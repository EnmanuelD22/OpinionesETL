"""Crea las dos cuentas SQL de la entrega con permisos acotados.

Las contraseñas se generan una sola vez y se guardan en LOCALAPPDATA, fuera de
Git. Ejecutar con una cuenta administradora de esta instancia de desarrollo.
"""

import os
from pathlib import Path
import secrets
import subprocess
from uuid import uuid4

import pyodbc

from config.settings import settings


WRITER = "opiniones_etl_writer"
READER = "opiniones_dw_reader"
SOURCE_ROLE = "rl_opiniones_fuente_lectura"
LOAD_ROLE = "rl_opiniones_dw_carga"
READ_ROLE = "rl_opiniones_dw_consulta"

SOURCE_TABLES = (
    "Opinion", "AnalisisOpinion", "Cliente", "Producto", "Categoria",
    "Fuente_Datos", "Clasificacion", "TipoOpinion",
)
DW_TABLES = (
    "Dim_Clasificacion", "Dim_TipoOpinion", "Dim_Cliente",
    "Dim_Producto", "Dim_Fuente", "Dim_Fecha", "Fact_Opinion",
)
DW_VIEWS = (
    "vw_KPIProductoMes", "vw_OpinionesDetalle", "vw_KPIGeneral",
    "vw_ClasificacionPorCanal",
)
LOAD_PROCEDURES = (
    "usp_StagingSocial_TVP", "usp_CargarEncuestasBulkStaging",
    "usp_PrepararResenasRelacionales", "usp_CargarDimClasificacion",
    "usp_CargarDimTipoOpinion", "usp_CargarDimCliente",
    "usp_CargarDimProducto", "usp_CargarDimFuente",
    "usp_CargarDimFecha", "usp_CargarFactOpinion",
)


def _credential_path() -> Path:
    local = os.getenv("LOCALAPPDATA")
    if os.name != "nt" or not local:
        raise RuntimeError("La instalación segura de credenciales requiere LOCALAPPDATA en Windows")
    path = (Path(local) / "OpinionesETL" / "sql_users.env").resolve()
    if not path.is_absolute() or path.is_relative_to(Path(__file__).resolve().parents[1]):
        raise RuntimeError("Las credenciales deben guardarse fuera del repositorio")
    return path


def _new_password() -> str:
    # Prefijo asegura las cuatro categorías de la política de Windows.
    return "Aa1!" + secrets.token_urlsafe(36)


def _read_credentials(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep or not key or not value or key in values:
            raise RuntimeError("Archivo local de credenciales inválido")
        values[key] = value
    required = {"OPINIONES_ETL_WRITER_PASSWORD", "OPINIONES_DW_READER_PASSWORD"}
    if set(values) != required:
        raise RuntimeError("Faltan contraseñas en el archivo local")
    return values


def _write_credentials(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write("# Credenciales locales de OpinionesETL; no copiar a Git.\n")
            for key, value in values.items():
                stream.write(f"{key}={value}\n")
        identity = subprocess.check_output(["whoami"], text=True).strip()
        subprocess.run(["icacls", str(temporary), "/grant:r", f"{identity}:(F)"],
                       check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["icacls", str(temporary), "/inheritance:r"],
                       check=True, stdout=subprocess.DEVNULL)
        if path.exists():
            raise RuntimeError("Otro proceso creó el archivo de credenciales")
        os.rename(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _odbc_value(value: str) -> str:
    return "{" + value.replace("}", "}}") + "}"


def _connection_string(database: str, *, username: str | None = None,
                       password: str | None = None) -> str:
    parts = [
        "DRIVER=" + _odbc_value(settings.db_driver),
        "SERVER=" + _odbc_value(settings.db_server),
        "DATABASE=" + _odbc_value(database),
        "Encrypt=yes",
        "TrustServerCertificate=" + ("yes" if settings.db_trust_server_certificate else "no"),
    ]
    if username is not None:
        parts.extend(("UID=" + _odbc_value(username),
                      "PWD=" + _odbc_value(password or "")))
    elif settings.db_trusted_connection:
        parts.append("Trusted_Connection=yes")
    else:
        parts.extend(("UID=" + _odbc_value(settings.db_user),
                      "PWD=" + _odbc_value(settings.db_password)))
    return ";".join(parts) + ";"


def _login_exists(cursor, name: str) -> bool:
    cursor.execute("SELECT 1 FROM sys.server_principals WHERE name = ?", name)
    return cursor.fetchone() is not None


def _check_existing_login(cursor, name: str) -> None:
    cursor.execute("SELECT is_policy_checked FROM sys.sql_logins WHERE name = ?", name)
    row = cursor.fetchone()
    if row is None or row[0] != 1:
        raise RuntimeError(f"El login existente {name} no es un SQL login con política activa")
    cursor.execute(
        "SELECT 1 FROM sys.server_role_members AS m "
        "JOIN sys.server_principals AS u ON u.principal_id = m.member_principal_id "
        "WHERE u.name = ?", name,
    )
    if cursor.fetchone() is not None:
        raise RuntimeError(f"El login existente {name} tiene un rol de servidor amplio")


def _allowed_role_grants(role: str) -> set[tuple[str, str, str]]:
    if role == SOURCE_ROLE:
        return {("SELECT", "OBJECT_OR_COLUMN", f"dbo.{table}")
                for table in SOURCE_TABLES}
    if role == LOAD_ROLE:
        allowed = {(permission, "OBJECT_OR_COLUMN", f"dbo.{table}")
                   for table in ("Stg_Opinion", "Stg_Rechazo")
                   for permission in ("SELECT", "INSERT", "DELETE")}
        allowed.update(("EXECUTE", "OBJECT_OR_COLUMN", f"dbo.{procedure}")
                       for procedure in LOAD_PROCEDURES)
        allowed.update((permission, "TYPE", "dbo.TVP_OpinionSocial")
                       for permission in ("EXECUTE", "REFERENCES"))
        return allowed
    if role == READ_ROLE:
        return {("SELECT", "OBJECT_OR_COLUMN", f"dbo.{name}")
                for name in (*DW_TABLES, *DW_VIEWS)}
    raise RuntimeError(f"Rol inesperado: {role}")


def _audit_database_permissions(cursor, principal: str,
                                allowed: set[tuple[str, str, str]]) -> None:
    cursor.execute(
        "SELECT p.permission_name, p.class_desc, p.state_desc, "
        "CASE WHEN p.class = 1 THEN "
        "  OBJECT_SCHEMA_NAME(p.major_id) + '.' + OBJECT_NAME(p.major_id) "
        "WHEN p.class = 6 THEN SCHEMA_NAME(t.schema_id) + '.' + t.name "
        "WHEN p.class = 3 THEN SCHEMA_NAME(p.major_id) "
        "WHEN p.class = 0 THEN DB_NAME() END AS destino "
        "FROM sys.database_permissions AS p "
        "JOIN sys.database_principals AS u ON u.principal_id = p.grantee_principal_id "
        "LEFT JOIN sys.types AS t ON p.class = 6 AND t.user_type_id = p.major_id "
        "WHERE u.name = ?", principal,
    )
    for permission, kind, state, target in cursor.fetchall():
        if state == "DENY":
            continue
        if state != "GRANT" or (permission, kind, target) not in allowed:
            raise RuntimeError(
                f"{principal} tiene un permiso inesperado: {permission} sobre {target}"
            )


def _audit_server_permissions(cursor, name: str) -> None:
    allowed = {"CONNECT SQL"}
    if name == WRITER:
        allowed.add("ADMINISTER BULK OPERATIONS")
    cursor.execute(
        "SELECT p.permission_name, p.state_desc "
        "FROM sys.server_permissions AS p "
        "JOIN sys.server_principals AS u ON u.principal_id = p.grantee_principal_id "
        "WHERE u.name = ?", name,
    )
    for permission, state in cursor.fetchall():
        if state == "DENY":
            continue
        if state != "GRANT" or permission not in allowed:
            raise RuntimeError(f"El login {name} tiene un permiso de servidor inesperado")


def _audit_database(cursor, database: str, existing: dict[str, bool]) -> None:
    cursor.execute(f"USE [{database}]")
    allowed_users = {WRITER}
    role_members = {SOURCE_ROLE: WRITER}
    if database == "OpinionesDW":
        allowed_users.add(READER)
        role_members = {LOAD_ROLE: WRITER, READ_ROLE: READER}

    for name, present in existing.items():
        if not present:
            continue
        cursor.execute("SELECT SUSER_SID(?)", name)
        sid = cursor.fetchone()[0]
        cursor.execute(
            "SELECT name, type FROM sys.database_principals WHERE sid = ?", sid,
        )
        aliases = cursor.fetchall()
        if any(alias != name or kind != "S" for alias, kind in aliases):
            raise RuntimeError(f"El login {name} tiene un usuario con otro nombre en {database}")
        if name not in allowed_users and aliases:
            raise RuntimeError(f"El lector tiene acceso no previsto a {database}")
        cursor.execute("SELECT sid, type FROM sys.database_principals WHERE name = ?", name)
        named = cursor.fetchone()
        if named is not None and (named[0] != sid or named[1] != "S"):
            raise RuntimeError(f"El usuario {name} está asociado a otra identidad")
        if named is not None:
            _audit_database_permissions(
                cursor, name, {("CONNECT", "DATABASE", database)}
            )
            cursor.execute(
                "SELECT r.name FROM sys.database_role_members AS m "
                "JOIN sys.database_principals AS r ON r.principal_id = m.role_principal_id "
                "JOIN sys.database_principals AS u ON u.principal_id = m.member_principal_id "
                "WHERE u.name = ?", name,
            )
            permitted_role = next((role for role, member in role_members.items()
                                   if member == name), None)
            if any(row[0] != permitted_role for row in cursor.fetchall()):
                raise RuntimeError(f"El usuario {name} tiene un rol adicional en {database}")

    for role, member in role_members.items():
        cursor.execute(
            "SELECT principal_id, type, owning_principal_id "
            "FROM sys.database_principals WHERE name = ?", role,
        )
        role_row = cursor.fetchone()
        if role_row is None:
            continue
        cursor.execute("SELECT USER_ID('dbo')")
        dbo_id = cursor.fetchone()[0]
        if role_row[1] != "R" or role_row[2] != dbo_id:
            raise RuntimeError(f"El rol existente {role} no pertenece a dbo")
        _audit_database_permissions(cursor, role, _allowed_role_grants(role))
        cursor.execute(
            "SELECT u.name FROM sys.database_role_members AS m "
            "JOIN sys.database_principals AS u ON u.principal_id = m.member_principal_id "
            "WHERE m.role_principal_id = ?", role_row[0],
        )
        if any(row[0] != member for row in cursor.fetchall()):
            raise RuntimeError(f"El rol {role} tiene un miembro inesperado")


def _preflight_security(cursor, existing: dict[str, bool]) -> None:
    for name, present in existing.items():
        if present:
            _audit_server_permissions(cursor, name)
    _audit_database(cursor, "OpinionesETL", existing)
    _audit_database(cursor, "OpinionesDW", existing)
    cursor.execute("USE [master]")


def _ensure_login(cursor, name: str, password: str, default_database: str) -> bool:
    if _login_exists(cursor, name):
        return False
    # Los identificadores son constantes de este módulo; se escapa el secreto.
    escaped = password.replace("'", "''")
    cursor.execute(
        f"CREATE LOGIN [{name}] WITH PASSWORD = '{escaped}', "
        f"CHECK_POLICY = ON, CHECK_EXPIRATION = OFF, "
        f"DEFAULT_DATABASE = [{default_database}]"
    )
    return True


def _ensure_user(cursor, name: str) -> None:
    cursor.execute("SELECT sid, type FROM sys.database_principals WHERE name = ?", name)
    row = cursor.fetchone()
    cursor.execute("SELECT SUSER_SID(?)", name)
    login_sid = cursor.fetchone()[0]
    if row is None:
        cursor.execute(f"CREATE USER [{name}] FOR LOGIN [{name}]")
    elif row[1] != "S" or row[0] != login_sid:
        raise RuntimeError(f"El usuario {name} existe con otra identidad")


def _ensure_role(cursor, role: str, member: str) -> None:
    cursor.execute("SELECT type FROM sys.database_principals WHERE name = ?", role)
    row = cursor.fetchone()
    if row is None:
        cursor.execute(f"CREATE ROLE [{role}] AUTHORIZATION [dbo]")
    elif row[0] != "R":
        raise RuntimeError(f"El nombre {role} no corresponde a un rol")
    cursor.execute(
        "SELECT 1 FROM sys.database_role_members AS m "
        "JOIN sys.database_principals AS r ON r.principal_id = m.role_principal_id "
        "JOIN sys.database_principals AS u ON u.principal_id = m.member_principal_id "
        "WHERE r.name = ? AND u.name = ?", role, member,
    )
    if cursor.fetchone() is None:
        cursor.execute(f"ALTER ROLE [{role}] ADD MEMBER [{member}]")


def _require_object(cursor, name: str, kind: str) -> None:
    cursor.execute("SELECT OBJECT_ID(?, ?)", f"dbo.{name}", kind)
    if cursor.fetchone()[0] is None:
        raise RuntimeError(f"Falta el objeto dbo.{name} requerido para los permisos")


def _grant_source(cursor) -> None:
    cursor.execute("USE [OpinionesETL]")
    cursor.execute("SELECT 1 FROM sys.database_principals WHERE name = ?", READER)
    if cursor.fetchone() is not None:
        raise RuntimeError("El lector ya tiene un usuario en OpinionesETL")
    _ensure_user(cursor, WRITER)
    _ensure_role(cursor, SOURCE_ROLE, WRITER)
    for table in SOURCE_TABLES:
        _require_object(cursor, table, "U")
        cursor.execute(f"GRANT SELECT ON OBJECT::dbo.[{table}] TO [{SOURCE_ROLE}]")


def _verify_login(name: str, password: str, database: str) -> None:
    try:
        connection = pyodbc.connect(
            _connection_string(database, username=name, password=password),
            timeout=10,
        )
    except pyodbc.Error:
        raise RuntimeError(
            f"La contraseña local no autentica al login existente {name}; "
            "no se modificaron sus permisos"
        ) from None
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT DB_NAME()")
        if cursor.fetchone()[0] != database:
            raise RuntimeError(f"La cuenta {name} abrió otra base de datos")
    finally:
        connection.close()


def _grant_warehouse(cursor) -> list[str]:
    cursor.execute("USE [OpinionesDW]")
    _ensure_user(cursor, WRITER)
    _ensure_user(cursor, READER)
    _ensure_role(cursor, LOAD_ROLE, WRITER)
    _ensure_role(cursor, READ_ROLE, READER)
    for table in ("Stg_Opinion", "Stg_Rechazo"):
        _require_object(cursor, table, "U")
        cursor.execute(
            f"GRANT SELECT, INSERT, DELETE ON OBJECT::dbo.[{table}] TO [{LOAD_ROLE}]"
        )
        cursor.execute(f"DENY SELECT ON OBJECT::dbo.[{table}] TO [{READER}]")
    cursor.execute(
        f"GRANT EXECUTE, REFERENCES ON TYPE::dbo.TVP_OpinionSocial TO [{LOAD_ROLE}]"
    )
    granted = []
    for procedure in LOAD_PROCEDURES:
        cursor.execute("SELECT OBJECT_ID(?, 'P')", f"dbo.{procedure}")
        if cursor.fetchone()[0] is not None:
            cursor.execute(
                f"GRANT EXECUTE ON OBJECT::dbo.[{procedure}] TO [{LOAD_ROLE}]"
            )
            granted.append(procedure)
    for table in DW_TABLES:
        _require_object(cursor, table, "U")
        cursor.execute(f"GRANT SELECT ON OBJECT::dbo.[{table}] TO [{READ_ROLE}]")
    for view in DW_VIEWS:
        _require_object(cursor, view, "V")
        cursor.execute(f"GRANT SELECT ON OBJECT::dbo.[{view}] TO [{READ_ROLE}]")
    cursor.execute(f"DENY INSERT, UPDATE, DELETE ON SCHEMA::dbo TO [{READER}]")
    return granted


def _verify_writer_permissions(password: str, procedures: list[str]) -> None:
    source = pyodbc.connect(
        _connection_string("OpinionesETL", username=WRITER, password=password),
        timeout=10,
    )
    try:
        cursor = source.cursor()
        for table in SOURCE_TABLES:
            cursor.execute(f"SELECT TOP (0) * FROM dbo.[{table}]")
    finally:
        source.close()

    warehouse = pyodbc.connect(
        _connection_string("OpinionesDW", username=WRITER, password=password),
        timeout=10,
    )
    try:
        cursor = warehouse.cursor()
        cursor.execute("SELECT permission_name FROM sys.fn_my_permissions(NULL, 'SERVER')")
        if "ADMINISTER BULK OPERATIONS" not in {row[0] for row in cursor.fetchall()}:
            raise RuntimeError("El usuario de carga no recibió permiso para BULK INSERT")
        cursor.execute(
            "SELECT permission_name FROM "
            "sys.fn_my_permissions('dbo.TVP_OpinionSocial', 'TYPE')"
        )
        type_permissions = {row[0] for row in cursor.fetchall()}
        if not {"EXECUTE", "REFERENCES"}.issubset(type_permissions):
            raise RuntimeError("El usuario de carga no puede usar el TVP")
        for procedure in procedures:
            cursor.execute("SELECT HAS_PERMS_BY_NAME(?, 'OBJECT', 'EXECUTE')",
                           f"dbo.{procedure}")
            if cursor.fetchone()[0] != 1:
                raise RuntimeError(f"Falta EXECUTE sobre {procedure}")

        batch_id = str(uuid4())
        cursor.execute(
            "INSERT INTO dbo.Stg_Opinion "
            "(IdEjecucion,IdTipoOpinion,IdOrigen,IdOpinion,IdCliente,IdProducto,"
            "Fecha,Comentario,IdFuente,Canal,Puntaje,IdClasificacion) "
            "VALUES (?,1,'PRUEBA_PERMISOS',2147483640,1,1,'2026-01-01',"
            "'Prueba de permisos',2,'Encuestas',5,1)", batch_id,
        )
        cursor.execute("DELETE FROM dbo.Stg_Opinion WHERE IdEjecucion = ?", batch_id)
        if cursor.rowcount != 1:
            raise RuntimeError("El usuario de carga no pudo borrar staging de opiniones")
        cursor.execute(
            "INSERT INTO dbo.Stg_Rechazo (IdEjecucion,Origen,IdOrigen,Motivo) "
            "VALUES (?,'encuesta','PRUEBA_PERMISOS','verificacion')", batch_id,
        )
        cursor.execute("DELETE FROM dbo.Stg_Rechazo WHERE IdEjecucion = ?", batch_id)
        if cursor.rowcount != 1:
            raise RuntimeError("El usuario de carga no pudo borrar staging de rechazos")

        if "usp_CargarDimClasificacion" in procedures:
            cursor.execute("EXEC dbo.usp_CargarDimClasificacion ?", batch_id)
            result = cursor.fetchone()
            if result is None or result[0] != 0:
                raise RuntimeError("La prueba de EXECUTE de dimensión no devolvió lote vacío")
    finally:
        warehouse.rollback()
        warehouse.close()


def _verify_reader_permissions(password: str) -> None:
    warehouse = pyodbc.connect(
        _connection_string("OpinionesDW", username=READER, password=password),
        timeout=10,
    )
    try:
        cursor = warehouse.cursor()
        for name in (*DW_TABLES, *DW_VIEWS):
            cursor.execute(f"SELECT TOP (0) * FROM dbo.[{name}]")
        for table in ("Fact_Opinion", "Dim_Cliente", "Stg_Opinion", "Stg_Rechazo"):
            for permission in ("INSERT", "UPDATE", "DELETE"):
                cursor.execute("SELECT HAS_PERMS_BY_NAME(?, 'OBJECT', ?)",
                               f"dbo.{table}", permission)
                if cursor.fetchone()[0] == 1:
                    raise RuntimeError(f"El lector tiene {permission} sobre {table}")
        for table in ("Stg_Opinion", "Stg_Rechazo"):
            cursor.execute("SELECT HAS_PERMS_BY_NAME(?, 'OBJECT', 'SELECT')",
                           f"dbo.{table}")
            if cursor.fetchone()[0] == 1:
                raise RuntimeError(f"El lector puede consultar {table}")
        for procedure in LOAD_PROCEDURES:
            cursor.execute("SELECT HAS_PERMS_BY_NAME(?, 'OBJECT', 'EXECUTE')",
                           f"dbo.{procedure}")
            if cursor.fetchone()[0] == 1:
                raise RuntimeError(f"El lector puede ejecutar {procedure}")
    finally:
        warehouse.close()

    try:
        source = pyodbc.connect(
            _connection_string("OpinionesETL", username=READER, password=password),
            timeout=5,
        )
    except pyodbc.Error:
        return
    source.close()
    raise RuntimeError("El lector puede abrir la base relacional")


def install() -> dict:
    credential_file = _credential_path()
    admin = pyodbc.connect(_connection_string("master"), autocommit=True, timeout=10)
    try:
        cursor = admin.cursor()
        existing = {name: _login_exists(cursor, name) for name in (WRITER, READER)}
        for name, present in existing.items():
            if present:
                _check_existing_login(cursor, name)
        _preflight_security(cursor, existing)
        if not credential_file.exists() and any(existing.values()):
            raise RuntimeError(
                "Existe un login con el nombre solicitado y no hay credenciales locales; "
                "no se cambiará su contraseña automáticamente"
            )
        if credential_file.exists():
            passwords = _read_credentials(credential_file)
        else:
            passwords = {
                "OPINIONES_ETL_WRITER_PASSWORD": _new_password(),
                "OPINIONES_DW_READER_PASSWORD": _new_password(),
            }
            _write_credentials(credential_file, passwords)

        if existing[WRITER]:
            _verify_login(WRITER, passwords["OPINIONES_ETL_WRITER_PASSWORD"],
                          "master")
        if existing[READER]:
            _verify_login(READER, passwords["OPINIONES_DW_READER_PASSWORD"],
                          "master")

        created_writer = _ensure_login(
            cursor, WRITER, passwords["OPINIONES_ETL_WRITER_PASSWORD"],
            "OpinionesETL",
        )
        created_reader = _ensure_login(
            cursor, READER, passwords["OPINIONES_DW_READER_PASSWORD"],
            "OpinionesDW",
        )
        cursor.execute(f"GRANT ADMINISTER BULK OPERATIONS TO [{WRITER}]")
        _grant_source(cursor)
        granted_procedures = _grant_warehouse(cursor)
    finally:
        admin.close()

    # Prueba conexiones y permisos efectivos con ambos logins, sin mostrar secretos.
    _verify_writer_permissions(passwords["OPINIONES_ETL_WRITER_PASSWORD"],
                               granted_procedures)
    _verify_reader_permissions(passwords["OPINIONES_DW_READER_PASSWORD"])

    return {
        "credenciales_locales": str(credential_file),
        "writer_creado": created_writer,
        "reader_creado": created_reader,
        "procedimientos_habilitados": granted_procedures,
    }


def main() -> None:
    result = install()
    print("Usuarios SQL configurados:")
    print(f"  {WRITER}: {'creado' if result['writer_creado'] else 'existente'}")
    print(f"  {READER}: {'creado' if result['reader_creado'] else 'existente'}")
    print(f"Credenciales locales: {result['credenciales_locales']}")
    print(f"Procedimientos habilitados: {len(result['procedimientos_habilitados'])}")


if __name__ == "__main__":
    main()
