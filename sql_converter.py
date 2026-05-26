"""
SQL Doğrulama ve Risk Analizi Motoru
INSERT → Doğrulama SELECT | UPDATE/DELETE → Risk Analizi SELECT
Oracle SQL uyumlu
"""

import re
from typing import Optional


# ─────────────────────────────────────────────────────────────
# YORUM TEMİZLEME
# ─────────────────────────────────────────────────────────────

def strip_comments(sql: str) -> str:
    result = []
    i = 0
    in_string = False
    n = len(sql)
    while i < n:
        c = sql[i]
        if in_string:
            result.append(c)
            if c == "'":
                if i + 1 < n and sql[i + 1] == "'":
                    result.append(sql[i + 1]); i += 2; continue
                in_string = False
        elif c == "'":
            in_string = True; result.append(c)
        elif c == '-' and i + 1 < n and sql[i + 1] == '-':
            while i < n and sql[i] != '\n':
                i += 1
            continue
        elif c == '/' and i + 1 < n and sql[i + 1] == '*':
            i += 2
            while i < n - 1:
                if sql[i] == '*' and sql[i + 1] == '/':
                    i += 2; break
                i += 1
            continue
        else:
            result.append(c)
        i += 1
    return ''.join(result)


# ─────────────────────────────────────────────────────────────
# İFADE BÖLME  (;  VEYA  YENİ SATIRDA INSERT/UPDATE/DELETE)
# ─────────────────────────────────────────────────────────────

_SPLIT_KW = frozenset(['INSERT', 'UPDATE', 'DELETE'])


def split_statements(sql: str) -> list:
    statements, current = [], []
    in_string = False
    depth = 0
    i = 0
    n = len(sql)

    while i < n:
        c = sql[i]

        if in_string:
            current.append(c)
            if c == "'":
                if i + 1 < n and sql[i + 1] == "'":
                    current.append(sql[i + 1]); i += 2; continue
                in_string = False
            i += 1; continue

        if c == "'":
            in_string = True; current.append(c); i += 1; continue

        if c == '(':
            depth += 1; current.append(c); i += 1; continue

        if c == ')':
            depth -= 1; current.append(c); i += 1; continue

        if c == ';':
            s = ''.join(current).strip()
            if s:
                statements.append(s)
            current = []; i += 1; continue

        # Otomatik bölme: noktalı virgül unutulmuşsa yeni satırda keyword ara
        if depth == 0 and (c.isalpha() or c == '_'):
            j = i
            while j < n and (sql[j].isalnum() or sql[j] == '_'):
                j += 1
            word = sql[i:j].upper()
            if word in _SPLIT_KW:
                existing = ''.join(current)
                existing_stripped = existing.strip()
                if existing_stripped:
                    trailing = existing.rstrip(' \t')
                    if trailing and trailing[-1] in '\n\r':
                        statements.append(existing_stripped)
                        current = []

        current.append(c)
        i += 1

    s = ''.join(current).strip()
    if s:
        statements.append(s)
    return statements


# ─────────────────────────────────────────────────────────────
# YARDIMCI FONKSİYONLAR
# ─────────────────────────────────────────────────────────────

def tokenize_csv(text: str) -> list:
    tokens, current, depth, in_string = [], '', 0, False
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if in_string:
            current += c
            if c == "'":
                if i + 1 < n and text[i + 1] == "'":
                    current += text[i + 1]; i += 2; continue
                in_string = False
        elif c == "'":
            in_string = True; current += c
        elif c == '(':
            depth += 1; current += c
        elif c == ')':
            depth -= 1; current += c
        elif c == ',' and depth == 0:
            tokens.append(current.strip()); current = ''
        else:
            current += c
        i += 1
    if current.strip():
        tokens.append(current.strip())
    return tokens


def escape_sql(text: str) -> str:
    return text.replace("'", "''")


def normalize_ws(sql: str) -> str:
    return re.sub(r'\s+', ' ', sql).strip()


def value_to_where(col: str, val: str) -> str:
    val = val.strip()
    upper = val.upper()
    if upper == 'SYSDATE':
        return f"TRUNC({col}) = TRUNC(SYSDATE)"
    elif upper == 'NULL':
        return f"{col} IS NULL"
    elif re.match(r'(?i)^(TO_DATE|TO_TIMESTAMP)\s*\(', val):
        return f"TRUNC({col}) = TRUNC({val})"
    elif re.match(r'(?i)^SYSTIMESTAMP\b', val):
        return f"TRUNC({col}) = TRUNC(SYSDATE)"
    elif val.startswith("'") and val.endswith("'"):
        return f"{col} = {val}"
    elif re.match(r'^-?\d+(\.\d+)?$', val):
        return f"{col} = {val}"
    else:
        return f"{col} = {val}"


# ─────────────────────────────────────────────────────────────
# İFADE TİPİ TESPİTİ
# ─────────────────────────────────────────────────────────────

_TYPE_MAP = {
    'INSERT':   'INSERT',
    'UPDATE':   'UPDATE',
    'DELETE':   'DELETE',
    'SELECT':   'SELECT',
    'CREATE':   'DDL',
    'ALTER':    'DDL',
    'DROP':     'DDL',
    'TRUNCATE': 'DDL',
    'RENAME':   'DDL',
    'COMMENT':  'DDL',
    'GRANT':    'DCL',
    'REVOKE':   'DCL',
    'COMMIT':   'TCL',
    'ROLLBACK': 'TCL',
    'SAVEPOINT':'TCL',
    'EXEC':     'EXEC',
    'EXECUTE':  'EXEC',
    'CALL':     'EXEC',
}


def stmt_type(stmt: str) -> str:
    first = stmt.strip().split()[0].upper() if stmt.strip() else ''
    return _TYPE_MAP.get(first, 'OTHER')


# ─────────────────────────────────────────────────────────────
# PARSE FONKSİYONLARI
# ─────────────────────────────────────────────────────────────

def parse_insert(stmt: str) -> Optional[dict]:
    stmt = stmt.strip()
    m = re.compile(
        r'(?i)INSERT\s+INTO\s+([\w."$]+(?:\.[\w."$]+)*)\s*\(([^)]+)\)\s*VALUES?\s*\('
    ).match(stmt)
    if not m:
        return None
    table = m.group(1).strip()
    cols  = [c.strip() for c in m.group(2).strip().split(',')]
    vals_start, depth, in_str, i = m.end(), 1, False, m.end()
    while i < len(stmt) and depth > 0:
        c = stmt[i]
        if in_str:
            if c == "'":
                if i + 1 < len(stmt) and stmt[i + 1] == "'": i += 2; continue
                in_str = False
        elif c == "'": in_str = True
        elif c == '(': depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0: break
        i += 1
    vals  = tokenize_csv(stmt[vals_start:i])
    error = None
    if len(cols) != len(vals):
        error = f'Sütun ({len(cols)}) ≠ Değer ({len(vals)}) sayısı'
    return {'type': 'INSERT', 'table': table, 'columns': cols, 'values': vals,
            'original': stmt, 'error': error}


def parse_update(stmt: str) -> Optional[dict]:
    stmt = stmt.strip()
    m = re.match(r'(?i)UPDATE\s+([\w."$]+(?:\.[\w."$]+)*)\s+SET\s+', stmt)
    if not m:
        return None
    table = m.group(1).strip()
    rest  = stmt[m.end():]
    wm    = re.search(r'\bWHERE\b', rest, re.IGNORECASE)
    if wm:
        set_clause, where_clause = rest[:wm.start()].strip(), rest[wm.end():].strip()
    else:
        set_clause, where_clause = rest.strip(), None
    return {'type': 'UPDATE', 'table': table, 'set_clause': set_clause,
            'where_clause': where_clause, 'original': stmt}


def parse_delete(stmt: str) -> Optional[dict]:
    stmt = stmt.strip()
    m = re.match(r'(?i)DELETE\s+(?:FROM\s+)?([\w."$]+(?:\.[\w."$]+)*)\s*', stmt)
    if not m:
        return None
    table = m.group(1).strip()
    rest  = stmt[m.end():]
    wm    = re.search(r'\bWHERE\b', rest, re.IGNORECASE)
    where_clause = rest[wm.end():].strip() if wm else None
    return {'type': 'DELETE', 'table': table, 'where_clause': where_clause,
            'original': stmt}


def _owner_name(full: str) -> tuple:
    """'SCHEMA.TABLE' → ('SCHEMA', 'TABLE')  |  'TABLE' → (None, 'TABLE')"""
    full = full.strip('"')
    if '.' in full:
        parts = full.split('.', 1)
        return parts[0].strip('"').upper(), parts[1].strip('"').upper()
    return None, full.upper()


def parse_ddl(stmt: str) -> Optional[dict]:
    """DDL ifadesini detaylı parse eder."""
    s = stmt.strip()
    base = {'original': s}

    # CREATE TABLE
    m = re.match(r'(?i)CREATE\s+TABLE\s+([\w."$]+(?:\.[\w."$]+)*)', s)
    if m:
        return {**base, 'action': 'CREATE', 'object_type': 'TABLE', 'name': m.group(1)}

    # CREATE [UNIQUE] INDEX name ON table
    m = re.match(r'(?i)CREATE\s+(?:UNIQUE\s+)?INDEX\s+([\w."$]+)\s+ON\s+([\w."$]+(?:\.[\w."$]+)*)', s)
    if m:
        return {**base, 'action': 'CREATE', 'object_type': 'INDEX',
                'name': m.group(1), 'on_table': m.group(2)}

    # CREATE OR REPLACE VIEW/PROCEDURE/FUNCTION/TRIGGER/PACKAGE
    m = re.match(
        r'(?i)CREATE\s+(?:OR\s+REPLACE\s+)?'
        r'(VIEW|PROCEDURE|FUNCTION|TRIGGER|PACKAGE(?:\s+BODY)?|TYPE(?:\s+BODY)?)\s+'
        r'([\w."$]+(?:\.[\w."$]+)*)', s)
    if m:
        return {**base, 'action': 'CREATE',
                'object_type': m.group(1).upper().split()[0],
                'name': m.group(2)}

    # DROP TABLE
    m = re.match(r'(?i)DROP\s+TABLE\s+([\w."$]+(?:\.[\w."$]+)*)', s)
    if m:
        return {**base, 'action': 'DROP', 'object_type': 'TABLE', 'name': m.group(1)}

    # DROP INDEX
    m = re.match(r'(?i)DROP\s+INDEX\s+([\w."$]+)', s)
    if m:
        return {**base, 'action': 'DROP', 'object_type': 'INDEX', 'name': m.group(1)}

    # DROP VIEW/PROCEDURE/FUNCTION/SEQUENCE
    m = re.match(r'(?i)DROP\s+(VIEW|PROCEDURE|FUNCTION|SEQUENCE|TRIGGER|PACKAGE|TYPE|SYNONYM)\s+'
                 r'([\w."$]+(?:\.[\w."$]+)*)', s)
    if m:
        return {**base, 'action': 'DROP',
                'object_type': m.group(1).upper(), 'name': m.group(2)}

    # TRUNCATE TABLE
    m = re.match(r'(?i)TRUNCATE\s+TABLE\s+([\w."$]+(?:\.[\w."$]+)*)', s)
    if m:
        return {**base, 'action': 'TRUNCATE', 'object_type': 'TABLE', 'name': m.group(1)}

    # ALTER TABLE … ADD (col TYPE)  — ADD CONSTRAINT ayrı yakalanır
    if re.match(r'(?i)ALTER\s+TABLE', s):
        tbl_m = re.match(r'(?i)ALTER\s+TABLE\s+([\w."$]+(?:\.[\w."$]+)*)\s+', s)
        tbl = tbl_m.group(1) if tbl_m else '?'
        rest = s[tbl_m.end():] if tbl_m else s

        # ADD CONSTRAINT
        mc = re.match(r'(?i)ADD\s+CONSTRAINT\s+([\w."$]+)', rest)
        if mc:
            return {**base, 'action': 'ALTER', 'object_type': 'TABLE', 'name': tbl,
                    'alter_op': 'ADD_CONSTRAINT', 'constraint': mc.group(1)}

        # ADD column
        mc = re.match(r'(?i)ADD\s+(?:COLUMN\s+)?\(?\s*([\w."$]+)', rest)
        if mc and 'CONSTRAINT' not in rest.upper()[:20]:
            return {**base, 'action': 'ALTER', 'object_type': 'TABLE', 'name': tbl,
                    'alter_op': 'ADD_COLUMN', 'column': mc.group(1)}

        # DROP COLUMN
        mc = re.match(r'(?i)DROP\s+COLUMN\s+([\w."$]+)', rest)
        if mc:
            return {**base, 'action': 'ALTER', 'object_type': 'TABLE', 'name': tbl,
                    'alter_op': 'DROP_COLUMN', 'column': mc.group(1)}

        # MODIFY
        mc = re.match(r'(?i)MODIFY\s+\(?\s*([\w."$]+)', rest)
        if mc:
            return {**base, 'action': 'ALTER', 'object_type': 'TABLE', 'name': tbl,
                    'alter_op': 'MODIFY_COLUMN', 'column': mc.group(1)}

        # RENAME COLUMN
        mc = re.match(r'(?i)RENAME\s+COLUMN\s+([\w."$]+)\s+TO\s+([\w."$]+)', rest)
        if mc:
            return {**base, 'action': 'ALTER', 'object_type': 'TABLE', 'name': tbl,
                    'alter_op': 'RENAME_COLUMN', 'column': mc.group(1), 'new_name': mc.group(2)}

        return {**base, 'action': 'ALTER', 'object_type': 'TABLE', 'name': tbl,
                'alter_op': 'GENERIC'}

    # Generic fallback
    m = re.match(
        r'(?i)(CREATE|ALTER|DROP|TRUNCATE|RENAME)\s+'
        r'(?:OR\s+REPLACE\s+)?'
        r'(TABLE|INDEX|VIEW|SEQUENCE|PROCEDURE|FUNCTION|TRIGGER|PACKAGE|TYPE|SYNONYM)?\s*'
        r'([\w."$]+(?:\.[\w."$]+)*)', s)
    if m:
        return {**base, 'action': m.group(1).upper(),
                'object_type': (m.group(2) or 'NESNE').upper(),
                'name': m.group(3)}
    return None


# ─────────────────────────────────────────────────────────────
# DDL DOĞRULAMA SELECT ÜRETECİ
# ─────────────────────────────────────────────────────────────

def generate_ddl_select(parsed: dict) -> Optional[str]:
    """
    Oracle data dictionary kullanarak DDL ön-kontrol SELECT'i üretir.
    CREATE  → nesne zaten var mı? (varsa hata verir)
    DROP    → nesne mevcut mu?   (yoksa hata verir)
    ALTER   → tablo/sütun var mı?
    TRUNCATE→ kritik uyarı
    """
    if not parsed:
        return None

    action   = parsed.get('action', '')
    obj_type = parsed.get('object_type', 'NESNE')
    name     = parsed.get('name', '?')
    kaynak   = escape_sql(normalize_ws(parsed['original']))
    owner, obj = _owner_name(name)
    ow_cond  = f" AND OWNER = '{owner}'" if owner else ''

    # ── CREATE TABLE ──
    if action == 'CREATE' and obj_type == 'TABLE':
        return (
            f"SELECT\n    '{kaynak}' AS KAYNAK,\n"
            f"    CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'FAIL' END AS STATUS,\n"
            f"    CASE\n"
            f"        WHEN COUNT(*) > 0 THEN 'HATA: {obj} tablosu zaten mevcut — CREATE başarısız olacak (ORA-00955)'\n"
            f"        ELSE 'OK: {obj} tablosu yok, oluşturulabilir'\n"
            f"    END AS SONUC\n"
            f"FROM ALL_TABLES\n"
            f"WHERE TABLE_NAME = '{obj}'{ow_cond}"
        )

    # ── CREATE INDEX ──
    if action == 'CREATE' and obj_type == 'INDEX':
        on_tbl_owner, _ = _owner_name(parsed.get('on_table', '')) if parsed.get('on_table') else (None, None)
        ow2 = f" AND TABLE_OWNER = '{on_tbl_owner}'" if on_tbl_owner else ''
        return (
            f"SELECT\n    '{kaynak}' AS KAYNAK,\n"
            f"    CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'FAIL' END AS STATUS,\n"
            f"    CASE\n"
            f"        WHEN COUNT(*) > 0 THEN 'HATA: {obj} index zaten mevcut — CREATE başarısız olacak (ORA-00955)'\n"
            f"        ELSE 'OK: {obj} index yok, oluşturulabilir'\n"
            f"    END AS SONUC\n"
            f"FROM ALL_INDEXES\n"
            f"WHERE INDEX_NAME = '{obj}'{ow2}"
        )

    # ── CREATE VIEW / PROCEDURE / FUNCTION vb. ──
    if action == 'CREATE' and obj_type not in ('TABLE', 'INDEX'):
        return (
            f"SELECT\n    '{kaynak}' AS KAYNAK,\n"
            f"    CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'FAIL' END AS STATUS,\n"
            f"    CASE\n"
            f"        WHEN COUNT(*) > 0 THEN 'UYARI: {obj} nesnesi zaten mevcut — OR REPLACE yoksa hata alınabilir'\n"
            f"        ELSE 'OK: {obj} nesnesi yok, oluşturulabilir'\n"
            f"    END AS SONUC\n"
            f"FROM ALL_OBJECTS\n"
            f"WHERE OBJECT_NAME = '{obj}' AND OBJECT_TYPE = '{obj_type}'{ow_cond}"
        )

    # ── DROP TABLE ──
    if action == 'DROP' and obj_type == 'TABLE':
        return (
            f"SELECT\n    '{kaynak}' AS KAYNAK,\n"
            f"    CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'FAIL' END AS STATUS,\n"
            f"    CASE\n"
            f"        WHEN COUNT(*) > 0 THEN 'OK: {obj} tablosu mevcut, DROP çalışacak'\n"
            f"        ELSE 'HATA: {obj} tablosu bulunamadı — DROP başarısız olacak (ORA-00942)'\n"
            f"    END AS SONUC\n"
            f"FROM ALL_TABLES\n"
            f"WHERE TABLE_NAME = '{obj}'{ow_cond}"
        )

    # ── DROP INDEX ──
    if action == 'DROP' and obj_type == 'INDEX':
        return (
            f"SELECT\n    '{kaynak}' AS KAYNAK,\n"
            f"    CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'FAIL' END AS STATUS,\n"
            f"    CASE\n"
            f"        WHEN COUNT(*) > 0 THEN 'OK: {obj} index mevcut, DROP çalışacak'\n"
            f"        ELSE 'HATA: {obj} index bulunamadı — DROP başarısız olacak'\n"
            f"    END AS SONUC\n"
            f"FROM ALL_INDEXES\n"
            f"WHERE INDEX_NAME = '{obj}'"
        )

    # ── DROP VIEW/PROCEDURE/FUNCTION vb. ──
    if action == 'DROP' and obj_type not in ('TABLE', 'INDEX'):
        return (
            f"SELECT\n    '{kaynak}' AS KAYNAK,\n"
            f"    CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'FAIL' END AS STATUS,\n"
            f"    CASE\n"
            f"        WHEN COUNT(*) > 0 THEN 'OK: {obj} nesnesi mevcut, DROP çalışacak'\n"
            f"        ELSE 'HATA: {obj} nesnesi bulunamadı — DROP başarısız olacak'\n"
            f"    END AS SONUC\n"
            f"FROM ALL_OBJECTS\n"
            f"WHERE OBJECT_NAME = '{obj}' AND OBJECT_TYPE = '{obj_type}'{ow_cond}"
        )

    # ── TRUNCATE TABLE ──
    if action == 'TRUNCATE':
        return (
            f"SELECT\n    '{kaynak}' AS KAYNAK,\n"
            f"    CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'FAIL' END AS STATUS,\n"
            f"    CASE\n"
            f"        WHEN COUNT(*) = 0 THEN 'UYARI: {obj} tablosu bulunamadı — TRUNCATE başarısız olacak'\n"
            f"        ELSE 'KRİTİK: {obj} tablosundaki TÜM veriler silinecek!'\n"
            f"    END AS SONUC\n"
            f"FROM ALL_TABLES\n"
            f"WHERE TABLE_NAME = '{obj}'{ow_cond}"
        )

    # ── ALTER TABLE ──
    if action == 'ALTER' and obj_type == 'TABLE':
        alter_op = parsed.get('alter_op', 'GENERIC')
        col      = (parsed.get('column') or '').strip('"').upper()
        t_owner, t_name = _owner_name(name)
        ow_t = f" AND OWNER = '{t_owner}'" if t_owner else ''

        if alter_op == 'ADD_COLUMN' and col:
            return (
                f"SELECT\n    '{kaynak}' AS KAYNAK,\n"
                f"    CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'FAIL' END AS STATUS,\n"
                f"    CASE\n"
                f"        WHEN COUNT(*) > 0 THEN 'HATA: {col} sütunu zaten mevcut — ADD başarısız olacak (ORA-01430)'\n"
                f"        ELSE 'OK: {col} sütunu yok, eklenebilir'\n"
                f"    END AS SONUC\n"
                f"FROM ALL_TAB_COLUMNS\n"
                f"WHERE TABLE_NAME = '{t_name}' AND COLUMN_NAME = '{col}'{ow_t}"
            )

        if alter_op == 'DROP_COLUMN' and col:
            return (
                f"SELECT\n    '{kaynak}' AS KAYNAK,\n"
                f"    CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'FAIL' END AS STATUS,\n"
                f"    CASE\n"
                f"        WHEN COUNT(*) > 0 THEN 'OK: {col} sütunu mevcut, DROP çalışacak'\n"
                f"        ELSE 'HATA: {col} sütunu bulunamadı — DROP başarısız olacak (ORA-00904)'\n"
                f"    END AS SONUC\n"
                f"FROM ALL_TAB_COLUMNS\n"
                f"WHERE TABLE_NAME = '{t_name}' AND COLUMN_NAME = '{col}'{ow_t}"
            )

        if alter_op == 'MODIFY_COLUMN' and col:
            return (
                f"SELECT\n    '{kaynak}' AS KAYNAK,\n"
                f"    CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'FAIL' END AS STATUS,\n"
                f"    CASE\n"
                f"        WHEN COUNT(*) > 0 THEN 'OK: {col} sütunu mevcut, MODIFY çalışacak'\n"
                f"        ELSE 'HATA: {col} sütunu bulunamadı — MODIFY başarısız olacak (ORA-00904)'\n"
                f"    END AS SONUC\n"
                f"FROM ALL_TAB_COLUMNS\n"
                f"WHERE TABLE_NAME = '{t_name}' AND COLUMN_NAME = '{col}'{ow_t}"
            )

        if alter_op == 'RENAME_COLUMN' and col:
            new_col = (parsed.get('new_name') or '').strip('"').upper()
            return (
                f"SELECT\n    '{kaynak}' AS KAYNAK,\n"
                f"    CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'FAIL' END AS STATUS,\n"
                f"    CASE\n"
                f"        WHEN COUNT(*) = 0 THEN 'HATA: {col} sütunu bulunamadı — RENAME başarısız olacak'\n"
                f"        ELSE 'OK: {col} sütunu mevcut, {new_col} olarak yeniden adlandırılabilir'\n"
                f"    END AS SONUC\n"
                f"FROM ALL_TAB_COLUMNS\n"
                f"WHERE TABLE_NAME = '{t_name}' AND COLUMN_NAME = '{col}'{ow_t}"
            )

        if alter_op == 'ADD_CONSTRAINT':
            cname = (parsed.get('constraint') or '').strip('"').upper()
            return (
                f"SELECT\n    '{kaynak}' AS KAYNAK,\n"
                f"    CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'FAIL' END AS STATUS,\n"
                f"    CASE\n"
                f"        WHEN COUNT(*) > 0 THEN 'HATA: {cname} constraint zaten mevcut'\n"
                f"        ELSE 'OK: {cname} constraint yok, eklenebilir'\n"
                f"    END AS SONUC\n"
                f"FROM ALL_CONSTRAINTS\n"
                f"WHERE CONSTRAINT_NAME = '{cname}'{ow_t}"
            )

        # Generic ALTER — sadece tablonun varlığını kontrol et
        return (
            f"SELECT\n    '{kaynak}' AS KAYNAK,\n"
            f"    CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'FAIL' END AS STATUS,\n"
            f"    CASE\n"
            f"        WHEN COUNT(*) > 0 THEN 'OK: {t_name} tablosu mevcut, ALTER çalışabilir'\n"
            f"        ELSE 'HATA: {t_name} tablosu bulunamadı — ALTER başarısız olacak (ORA-00942)'\n"
            f"    END AS SONUC\n"
            f"FROM ALL_TABLES\n"
            f"WHERE TABLE_NAME = '{t_name}'{ow_t}"
        )

    return None


# ─────────────────────────────────────────────────────────────
# SELECT ÜRETİCİLER
# ─────────────────────────────────────────────────────────────

def generate_insert_select(parsed: dict) -> str:
    kaynak = escape_sql(normalize_ws(parsed['original']))
    if parsed.get('error'):
        return (f"SELECT\n    '{kaynak}' AS KAYNAK,\n"
                f"    'FAIL'                               AS STATUS,\n"
                f"    'PARSE HATASI: {parsed['error']}' AS SONUC\nFROM DUAL")
    cols, vals, table = parsed['columns'], parsed['values'], parsed['table']
    where = '\n    AND '.join(value_to_where(c, v) for c, v in zip(cols, vals))
    return (f"SELECT\n    '{kaynak}' AS KAYNAK,\n"
            f"    CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'FAIL' END AS STATUS,\n"
            f"    CASE\n        WHEN COUNT(*) > 0 THEN 'OK'\n        ELSE 'FAIL'\n    END AS SONUC\n"
            f"FROM {table}\nWHERE {where}")


def generate_update_select(parsed: dict) -> str:
    table, where = parsed['table'], parsed['where_clause']
    kaynak = escape_sql(normalize_ws(parsed['original']))
    if where:
        where_part = f"WHERE {where}"
        status_line = "    CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'FAIL' END AS STATUS,\n"
        case_lines = (
            "        WHEN COUNT(*) = 0  THEN 'UYARI: Güncellenecek kayıt bulunamadı'\n"
            "        WHEN COUNT(*) <= 10  THEN 'DÜŞÜK RİSK: ' || TO_CHAR(COUNT(*)) || ' satır güncellenecek'\n"
            "        WHEN COUNT(*) <= 100 THEN 'ORTA RİSK: ' || TO_CHAR(COUNT(*)) || ' satır güncellenecek'\n"
            "        ELSE 'YÜKSEK RİSK: ' || TO_CHAR(COUNT(*)) || ' satır güncellenecek!'"
        )
    else:
        where_part = "/* 1=1   <<< UYARI: WHERE KOŞULU YOK – TÜM TABLO ETKİLENECEK >>> */"
        status_line = "    CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'FAIL' END AS STATUS,\n"
        case_lines = (
            "        WHEN COUNT(*) = 0 THEN 'KRİTİK [WHERE YOK] → Tablo zaten boş'\n"
            "        ELSE 'KRİTİK [WHERE YOK] → Tablodaki TÜM ' || TO_CHAR(COUNT(*)) || ' SATIR GÜNCELLENECEKTİR!'"
        )
    return (f"SELECT\n    '{kaynak}' AS KAYNAK,\n"
            f"{status_line}"
            f"    CASE\n{case_lines}\n    END AS SONUC\n"
            f"FROM {table}\n{where_part}")


def generate_delete_select(parsed: dict) -> str:
    table, where = parsed['table'], parsed['where_clause']
    kaynak = escape_sql(normalize_ws(parsed['original']))
    if where:
        where_part = f"WHERE {where}"
        status_line = "    CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'FAIL' END AS STATUS,\n"
        case_lines = (
            "        WHEN COUNT(*) = 0  THEN 'UYARI: Silinecek kayıt bulunamadı'\n"
            "        WHEN COUNT(*) <= 10  THEN 'DÜŞÜK RİSK: ' || TO_CHAR(COUNT(*)) || ' satır silinecek'\n"
            "        WHEN COUNT(*) <= 100 THEN 'ORTA RİSK: ' || TO_CHAR(COUNT(*)) || ' satır silinecek'\n"
            "        ELSE 'YÜKSEK RİSK: ' || TO_CHAR(COUNT(*)) || ' satır silinecek!'"
        )
    else:
        where_part = "/* 1=1   <<< UYARI: WHERE KOŞULU YOK – TÜM TABLO SİLİNECEK >>> */"
        status_line = "    CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'FAIL' END AS STATUS,\n"
        case_lines = (
            "        WHEN COUNT(*) = 0 THEN 'KRİTİK [WHERE YOK] → Tablo zaten boş'\n"
            "        ELSE 'KRİTİK [WHERE YOK] → Tablodaki TÜM ' || TO_CHAR(COUNT(*)) || ' SATIR SİLİNECEKTİR!'"
        )
    return (f"SELECT\n    '{kaynak}' AS KAYNAK,\n"
            f"{status_line}"
            f"    CASE\n{case_lines}\n    END AS SONUC\n"
            f"FROM {table}\n{where_part}")


# ─────────────────────────────────────────────────────────────
# EXEC / EXECUTE / CALL PARSE & SELECT
# ─────────────────────────────────────────────────────────────

def parse_exec(stmt: str) -> Optional[dict]:
    """EXEC / EXECUTE / CALL ifadesini parse eder."""
    stmt = stmt.strip()
    m = re.match(
        r'(?i)(?:EXEC(?:UTE)?|CALL)\s+([\w."$]+(?:\.[\w."$]+)*)\s*(\(.*)?$',
        stmt, re.DOTALL
    )
    if not m:
        return None

    full_name = m.group(1).strip()
    parts = [p.strip('"').upper() for p in full_name.split('.')]

    owner = package = proc = None
    if len(parts) == 1:
        proc = parts[0]
    elif len(parts) == 2:
        owner, proc = parts[0], parts[1]
    elif len(parts) >= 3:
        owner, package, proc = parts[0], parts[1], parts[2]

    return {
        'type': 'EXEC',
        'owner': owner,
        'package': package,
        'proc': proc,
        'full_name': full_name,
        'original': stmt,
    }


def generate_exec_select(parsed: dict) -> str:
    kaynak  = escape_sql(normalize_ws(parsed['original']))
    owner   = parsed.get('owner')
    package = parsed.get('package')
    proc    = parsed['proc']
    ow_cond = f" AND OWNER = '{owner}'" if owner else ''

    if package:
        # 3-part: SCHEMA.PACKAGE.PROC
        display = f"{package}.{proc}"
        return (
            f"SELECT\n    '{kaynak}' AS KAYNAK,\n"
            f"    CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'FAIL' END AS STATUS,\n"
            f"    CASE\n"
            f"        WHEN COUNT(*) > 0 THEN 'OK: {display} paket prosedürü mevcut'\n"
            f"        ELSE 'HATA: {display} bulunamadı — EXEC başarısız olacak'\n"
            f"    END AS SONUC\n"
            f"FROM ALL_PROCEDURES\n"
            f"WHERE OBJECT_NAME = '{package}' AND PROCEDURE_NAME = '{proc}'{ow_cond}"
        )
    elif owner:
        # 2-part: SCHEMA.PROC — hem standalone hem paket alt-prosedürü olabilir
        display = f"{owner}.{proc}"
        return (
            f"SELECT\n    '{kaynak}' AS KAYNAK,\n"
            f"    CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'FAIL' END AS STATUS,\n"
            f"    CASE\n"
            f"        WHEN COUNT(*) > 0 THEN 'OK: {display} prosedürü/fonksiyonu mevcut'\n"
            f"        ELSE 'HATA: {display} bulunamadı — EXEC başarısız olacak'\n"
            f"    END AS SONUC\n"
            f"FROM ALL_PROCEDURES\n"
            f"WHERE OWNER = '{owner}'\n"
            f"  AND (OBJECT_NAME = '{proc}' OR PROCEDURE_NAME = '{proc}')"
        )
    else:
        # Sadece prosedür adı — standalone kontrol
        return (
            f"SELECT\n    '{kaynak}' AS KAYNAK,\n"
            f"    CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'FAIL' END AS STATUS,\n"
            f"    CASE\n"
            f"        WHEN COUNT(*) > 0 THEN 'OK: {proc} prosedürü/fonksiyonu mevcut'\n"
            f"        ELSE 'HATA: {proc} bulunamadı — EXEC başarısız olacak'\n"
            f"    END AS SONUC\n"
            f"FROM ALL_PROCEDURES\n"
            f"WHERE OBJECT_NAME = '{proc}' AND PROCEDURE_NAME IS NULL"
        )


# ─────────────────────────────────────────────────────────────
# ANA DÖNÜŞÜM
# ─────────────────────────────────────────────────────────────

def convert_sql(sql_text: str) -> dict:
    cleaned   = strip_comments(sql_text)
    raw_stmts = split_statements(cleaned)

    selects, statement_list, errors = [], [], []
    stats = {'insert': 0, 'update': 0, 'delete': 0, 'ddl': 0, 'other': 0, 'errors': 0}

    for raw in raw_stmts:
        raw = raw.strip()
        if not raw:
            continue

        stype = stmt_type(raw)
        first_word = raw.split()[0].upper()

        # ── INSERT ──
        if stype == 'INSERT':
            parsed = parse_insert(raw)
            if parsed:
                stats['insert'] += 1
                sel = generate_insert_select(parsed)
                selects.append(sel)
                statement_list.append({
                    'type': 'INSERT', 'table': parsed['table'],
                    'original': raw, 'original_short': normalize_ws(raw)[:90],
                    'select': sel, 'risk': 'DOGRULAMA', 'has_where': None,
                    'note': f"{len(parsed['columns'])} sütun",
                })
                if parsed.get('error'):
                    stats['errors'] += 1; errors.append(parsed['error'])
            else:
                stats['errors'] += 1; errors.append(f"INSERT parse hatası: {raw[:80]}")

        # ── UPDATE ──
        elif stype == 'UPDATE':
            parsed = parse_update(raw)
            if parsed:
                stats['update'] += 1
                sel = generate_update_select(parsed)
                selects.append(sel)
                has_where = parsed['where_clause'] is not None
                statement_list.append({
                    'type': 'UPDATE', 'table': parsed['table'],
                    'original': raw, 'original_short': normalize_ws(raw)[:90],
                    'select': sel,
                    'risk': 'WHERE_VAR' if has_where else 'KRITIK',
                    'has_where': has_where,
                    'note': f"WHERE: {parsed['where_clause'][:50]}" if has_where else 'WHERE koşulu yok!',
                })
            else:
                stats['errors'] += 1; errors.append(f"UPDATE parse hatası: {raw[:80]}")

        # ── DELETE ──
        elif stype == 'DELETE':
            parsed = parse_delete(raw)
            if parsed:
                stats['delete'] += 1
                sel = generate_delete_select(parsed)
                selects.append(sel)
                has_where = parsed['where_clause'] is not None
                statement_list.append({
                    'type': 'DELETE', 'table': parsed['table'],
                    'original': raw, 'original_short': normalize_ws(raw)[:90],
                    'select': sel,
                    'risk': 'WHERE_VAR' if has_where else 'KRITIK',
                    'has_where': has_where,
                    'note': f"WHERE: {parsed['where_clause'][:50]}" if has_where else 'WHERE koşulu yok!',
                })
            else:
                stats['errors'] += 1; errors.append(f"DELETE parse hatası: {raw[:80]}")

        # ── EXEC / EXECUTE / CALL ──
        elif stype == 'EXEC':
            parsed = parse_exec(raw)
            if parsed:
                stats['other'] += 1
                sel = generate_exec_select(parsed)
                selects.append(sel)
                proc_label = parsed['full_name']
                statement_list.append({
                    'type': 'EXEC', 'table': proc_label,
                    'original': raw, 'original_short': normalize_ws(raw)[:90],
                    'select': sel, 'risk': 'PROC', 'has_where': None,
                    'note': f"Prosedür: {proc_label}",
                })
            else:
                stats['errors'] += 1; errors.append(f"EXEC parse hatası: {raw[:80]}")

        # ── DDL (CREATE / ALTER / DROP / TRUNCATE ...) ──
        elif stype == 'DDL':
            stats['ddl'] += 1
            p = parse_ddl(raw)
            if p:
                tbl        = p['name']
                otype      = p.get('object_type', 'NESNE')
                alter_op   = p.get('alter_op')
                col        = p.get('column', '')
                new_name   = p.get('new_name', '')
                cname      = p.get('constraint', '')
                ddl_sel    = generate_ddl_select(p)
                if ddl_sel:
                    selects.append(ddl_sel)
                if alter_op and col:
                    note = {
                        'ADD_COLUMN':    f'ADD {col}',
                        'DROP_COLUMN':   f'DROP COLUMN {col}',
                        'MODIFY_COLUMN': f'MODIFY {col}',
                        'RENAME_COLUMN': f'RENAME {col} → {new_name}',
                        'ADD_CONSTRAINT':f'ADD CONSTRAINT {cname}',
                    }.get(alter_op, otype)
                else:
                    note = otype
            else:
                tbl, otype, ddl_sel, note = '?', 'NESNE', None, 'NESNE'

            statement_list.append({
                'type': first_word,
                'table': tbl,
                'original': raw, 'original_short': normalize_ws(raw)[:90],
                'select': ddl_sel,
                'risk': 'DDL',
                'has_where': None,
                'note': note,
                'has_check': ddl_sel is not None,
            })

        # ── Diğer (SELECT, COMMIT, ROLLBACK, vs.) — sayılmaz, atlanır ──
        else:
            pass

    # Tablo özeti — sadece DML işlemleri
    table_summary: dict = {}
    for s in statement_list:
        if s['type'] in ('INSERT', 'UPDATE', 'DELETE'):
            tbl = s['table']
            if tbl not in table_summary:
                table_summary[tbl] = {'INSERT': 0, 'UPDATE': 0, 'DELETE': 0}
            table_summary[tbl][s['type']] += 1

    stats['total'] = len(statement_list)

    return {
        'selects': selects,
        'statements': statement_list,
        'stats': stats,
        'errors': errors,
        'table_summary': table_summary,
    }


def format_output(result: dict) -> str:
    if not result['selects']:
        return "-- Dönüştürülecek INSERT/UPDATE/DELETE ifadesi bulunamadı."
    s = result['stats']
    lines = [
        "-- ================================================================",
        "--  OTOMATİK OLUŞTURULAN DOĞRULAMA / RİSK ANALİZİ SORGUSU",
        f"--  INSERT: {s['insert']}  |  UPDATE: {s['update']}  |  DELETE: {s['delete']}  |  DDL: {s['ddl']}  |  Diğer: {s['other']}",
        "-- ================================================================",
    ]
    kritik = [st for st in result['statements'] if st['risk'] == 'KRITIK']
    if kritik:
        lines.append(f"-- !! KRİTİK: {len(kritik)} adet WHERE KOŞULSUZ ifade var !!")
    for err in result['errors']:
        lines.append(f"-- UYARI: {err}")
    lines.append("")
    lines.append('\nUNION ALL\n'.join(result['selects']))
    lines.append(';')
    return '\n'.join(lines)
