import os
import sys
from textwrap import indent

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "paint_shop.settings")

try:
    import django  # type: ignore
    django.setup()
except Exception as exc:  # pragma: no cover
    print(f"Failed to setup Django: {exc}")
    sys.exit(1)

from django.db import connection  # type: ignore


def fetchall_dict(cursor, query, params=None):
    cursor.execute(query, params or [])
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def type_with_length(col):
    data_type = col["data_type"]
    # Prefer udt_name for specificity (e.g., int8) but normalize common types
    udt_name = col.get("udt_name") or data_type
    char_len = col.get("character_maximum_length")
    num_prec = col.get("numeric_precision")
    num_scale = col.get("numeric_scale")

    # Map some common udt names to canonical SQL types
    udt_map = {
        "int2": "smallint",
        "int4": "integer",
        "int8": "bigint",
        "varchar": "varchar",
        "bpchar": "char",
        "text": "text",
        "bool": "boolean",
        "timestamp": "timestamp",
        "timestamptz": "timestamptz",
        "date": "date",
        "numeric": "numeric",
        "float4": "real",
        "float8": "double precision",
        "uuid": "uuid",
        "jsonb": "jsonb",
        "bytea": "bytea",
    }

    base = udt_map.get(udt_name, udt_name or data_type)

    if base in ("varchar", "char") and char_len:
        return f"{base}({char_len})"
    if base == "numeric" and num_prec:
        if num_scale is not None:
            return f"numeric({num_prec},{num_scale})"
        return f"numeric({num_prec})"
    return base


def main():
    with connection.cursor() as cursor:
        # Get user tables in public schema ordered for readability
        tables = fetchall_dict(
            cursor,
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema='public' AND table_type='BASE TABLE'
            ORDER BY table_name
            """,
        )

        # Columns metadata
        columns = fetchall_dict(
            cursor,
            """
            SELECT table_name, column_name, is_nullable, column_default,
                   data_type, udt_name,
                   character_maximum_length, numeric_precision, numeric_scale
            FROM information_schema.columns
            WHERE table_schema='public'
            ORDER BY table_name, ordinal_position
            """,
        )

        # Primary keys
        pks = fetchall_dict(
            cursor,
            """
            SELECT kc.table_name, kc.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kc
                 ON tc.constraint_name = kc.constraint_name
                AND tc.table_schema   = kc.table_schema
                AND tc.table_name     = kc.table_name
            WHERE tc.table_schema='public' AND tc.constraint_type='PRIMARY KEY'
            ORDER BY kc.table_name, kc.ordinal_position
            """,
        )

        # Foreign keys
        fks = fetchall_dict(
            cursor,
            """
            SELECT tc.table_name,
                   kcu.column_name,
                   ccu.table_name   AS foreign_table_name,
                   ccu.column_name  AS foreign_column_name,
                   tc.constraint_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                 ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema   = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                 ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema   = tc.table_schema
            WHERE tc.table_schema='public' AND tc.constraint_type = 'FOREIGN KEY'
            ORDER BY tc.table_name, kcu.ordinal_position
            """,
        )

    # Organize metadata
    cols_by_table = {}
    for c in columns:
        cols_by_table.setdefault(c["table_name"], []).append(c)

    pks_by_table = {}
    for pk in pks:
        pks_by_table.setdefault(pk["table_name"], []).append(pk["column_name"])

    fks_by_table = {}
    for fk in fks:
        fks_by_table.setdefault(fk["table_name"], []).append(fk)

    # Build SQL script
    lines = []
    lines.append("-- Database schema dump (public schema)\n")
    for t in tables:
        table = t["table_name"]
        lines.append(f"--\n-- Table: {table}\n--")
        lines.append(f"CREATE TABLE IF NOT EXISTS \"{table}\" (")

        col_lines = []
        for col in cols_by_table.get(table, []):
            col_def = [f'"{col["column_name"]}" {type_with_length(col)}']
            if col["is_nullable"] == "NO":
                col_def.append("NOT NULL")
            if col["column_default"]:
                default = col["column_default"].strip()
                col_def.append(f"DEFAULT {default}")
            col_lines.append(" ".join(col_def))

        # Primary key constraint
        pk_cols = pks_by_table.get(table)
        if pk_cols:
            pk = ", ".join(f'"{c}"' for c in pk_cols)
            col_lines.append(f"PRIMARY KEY ({pk})")

        lines.append(indent(",\n".join(col_lines), "    "))
        lines.append(");\n")

        # Foreign keys as separate ALTER statements for clarity
        for fk in fks_by_table.get(table, []):
            cname = fk["constraint_name"]
            ccol = fk["column_name"]
            ftab = fk["foreign_table_name"]
            fcol = fk["foreign_column_name"]
            lines.append(
                f"ALTER TABLE \"{table}\"\n"
                f"    ADD CONSTRAINT \"{cname}\" FOREIGN KEY (\"{ccol}\")\n"
                f"    REFERENCES \"{ftab}\" (\"{fcol}\");\n"
            )

    content = "\n".join(lines)

    md_lines = []
    md_lines.append("# Database Schema (public)\n")
    md_lines.append("Generated from live PostgreSQL via Django connection.\n")
    md_lines.append("```sql")
    md_lines.append(content)
    md_lines.append("``" )

    out_path = os.path.join(os.path.dirname(__file__), "..", "DB_SCHEMA.md")
    out_path = os.path.abspath(out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"Wrote schema to {out_path}")


if __name__ == "__main__":
    main()



