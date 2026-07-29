import os
import sqlite3
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from csv_parser import Employee, TaxRecord

log = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "app.db")
os.makedirs(DATA_DIR, exist_ok=True)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pin TEXT NOT NULL,
            fiscal_year TEXT NOT NULL,
            start_year INTEGER NOT NULL,
            end_year INTEGER NOT NULL,
            name TEXT,
            designation TEXT,
            department TEXT,
            gender TEXT,
            tin TEXT,
            monthly_salary TEXT,
            festival_bonus REAL DEFAULT 0.0,
            arrears REAL DEFAULT 0.0,
            others REAL DEFAULT 0.0,
            gross REAL DEFAULT 0.0,
            net_total REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(pin, fiscal_year)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tax_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pin TEXT NOT NULL,
            fiscal_year TEXT NOT NULL,
            start_year INTEGER NOT NULL,
            end_year INTEGER NOT NULL,
            month TEXT,
            challan_no TEXT,
            challan_date TEXT,
            claim_amount REAL DEFAULT 0.0,
            total_challan_amount REAL DEFAULT 0.0,
            bank_info TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_emp_pin_fy ON employees(pin, fiscal_year);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_emp_dept ON employees(department);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tax_pin_fy ON tax_records(pin, fiscal_year);")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS dataset_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT UNIQUE NOT NULL,
            fiscal_year TEXT NOT NULL,
            dataset_type TEXT NOT NULL,
            filename TEXT NOT NULL,
            record_count INTEGER NOT NULL DEFAULT 0,
            file_size_bytes INTEGER DEFAULT 0,
            uploaded_by TEXT DEFAULT 'admin',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_emp_fy ON employees(fiscal_year);
        """)
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tax_fy ON tax_records(fiscal_year);
        """)
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tax_pin ON tax_records(pin);
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tax_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            req_id TEXT UNIQUE NOT NULL,
            pin TEXT NOT NULL,
            name TEXT NOT NULL,
            designation TEXT,
            tin TEXT,
            email TEXT NOT NULL,
            fiscal_year TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            remarks TEXT,
            hr_notes TEXT,
            prepared_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_req_pin ON tax_requests(pin);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_req_status ON tax_requests(status);")
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_batches_fy ON dataset_batches(fiscal_year);
        """)

        # Seed initial sample tax requests if table is empty
        cursor.execute("SELECT COUNT(*) FROM tax_requests;")
        if cursor.fetchone()[0] == 0:
            sample_reqs = [
                ("REQ-20260729-1001", "10100", "Wasik Ahmed Khan", "Software Engineer", "123456789012", "wasik.ahmed@brac.net", "2024-2025", "Pending", "Requesting certificate for bank loan verification"),
                ("REQ-20260729-1002", "10102", "Jane Smith", "Assistant Director", "987654321098", "jane.smith@brac.net", "2024-2025", "In Progress", "Needs physical signed copy"),
                ("REQ-20260729-1003", "10101", "Md. Tanvir Hossain", "Senior Finance Officer", "456789012345", "tanvir.hossain@brac.net", "2024-2025", "Ready for Pickup", "Certificate prepared & signed")
            ]
            cursor.executemany("""
                INSERT INTO tax_requests (req_id, pin, name, designation, tin, email, fiscal_year, status, remarks)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, sample_reqs)

        # Seed initial sample employees & tax records if employees table is empty
        cursor.execute("SELECT COUNT(*) FROM employees;")
        if cursor.fetchone()[0] == 0:
            sample_emps = [
                ("10100", "2024-2025", 2024, 2025, "Wasik Ahmed Khan", "Software Engineer", "BRAC IED", "Male", "123456789012", '{"Jul": 80000, "Aug": 80000, "Sep": 80000, "Oct": 80000, "Nov": 80000, "Dec": 80000, "Jan": 85000, "Feb": 85000, "Mar": 85000, "Apr": 85000, "May": 85000, "Jun": 85000}', 160000.0, 0.0, 0.0, 1150000.0, 1150000.0),
                ("10101", "2024-2025", 2024, 2025, "Md. Tanvir Hossain", "Senior Finance Officer", "BRAC IED", "Male", "456789012345", '{"Jul": 65000, "Aug": 65000, "Sep": 65000, "Oct": 65000, "Nov": 65000, "Dec": 65000, "Jan": 70000, "Feb": 70000, "Mar": 70000, "Apr": 70000, "May": 70000, "Jun": 70000}', 135000.0, 0.0, 0.0, 945000.0, 945000.0),
                ("10102", "2024-2025", 2024, 2025, "Jane Smith", "Assistant Director", "BRAC IED", "Female", "987654321098", '{"Jul": 95000, "Aug": 95000, "Sep": 95000, "Oct": 95000, "Nov": 95000, "Dec": 95000, "Jan": 100000, "Feb": 100000, "Mar": 100000, "Apr": 100000, "May": 100000, "Jun": 100000}', 195000.0, 0.0, 0.0, 1365000.0, 1365000.0),
                ("10103", "2024-2025", 2024, 2025, "Anisur Rahman", "Audit Supervisor", "BRAC IED", "Male", "345678901234", '{"Jul": 60000, "Aug": 60000, "Sep": 60000, "Oct": 60000, "Nov": 60000, "Dec": 60000, "Jan": 62000, "Feb": 62000, "Mar": 62000, "Apr": 62000, "May": 62000, "Jun": 62000}', 122000.0, 0.0, 0.0, 854000.0, 854000.0),
                
                ("10100", "2025-2026", 2025, 2026, "Wasik Ahmed Khan", "Software Engineer", "BRAC IED", "Male", "123456789012", '{"Jul": 90000, "Aug": 90000, "Sep": 90000, "Oct": 90000, "Nov": 90000, "Dec": 90000, "Jan": 95000, "Feb": 95000, "Mar": 95000, "Apr": 95000, "May": 95000, "Jun": 95000}', 185000.0, 0.0, 0.0, 1295000.0, 1295000.0),
                ("10101", "2025-2026", 2025, 2026, "Md. Tanvir Hossain", "Senior Finance Officer", "BRAC IED", "Male", "456789012345", '{"Jul": 72000, "Aug": 72000, "Sep": 72000, "Oct": 72000, "Nov": 72000, "Dec": 72000, "Jan": 75000, "Feb": 75000, "Mar": 75000, "Apr": 75000, "May": 75000, "Jun": 75000}', 147000.0, 0.0, 0.0, 1029000.0, 1029000.0),
                ("10102", "2025-2026", 2025, 2026, "Jane Smith", "Assistant Director", "BRAC IED", "Female", "987654321098", '{"Jul": 105000, "Aug": 105000, "Sep": 105000, "Oct": 105000, "Nov": 105000, "Dec": 105000, "Jan": 110000, "Feb": 110000, "Mar": 110000, "Apr": 110000, "May": 110000, "Jun": 110000}', 215000.0, 0.0, 0.0, 1505000.0, 1505000.0),
                ("10103", "2025-2026", 2025, 2026, "Anisur Rahman", "Audit Supervisor", "BRAC IED", "Male", "345678901234", '{"Jul": 65000, "Aug": 65000, "Sep": 65000, "Oct": 65000, "Nov": 65000, "Dec": 65000, "Jan": 68000, "Feb": 68000, "Mar": 68000, "Apr": 68000, "May": 68000, "Jun": 68000}', 133000.0, 0.0, 0.0, 931000.0, 931000.0)
            ]
            cursor.executemany("""
                INSERT INTO employees (
                    pin, fiscal_year, start_year, end_year, name, designation, department,
                    gender, tin, monthly_salary, festival_bonus, arrears, others, gross, net_total
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, sample_emps)

            sample_tax = [
                ("10100", "2024-2025", 2024, 2025, "Dec 2024", "CH-2024-101", "15/12/2024", 5000.0, 60000.0, "Sonali Bank, Dhaka"),
                ("10101", "2024-2025", 2024, 2025, "Dec 2024", "CH-2024-102", "15/12/2024", 3500.0, 42000.0, "Sonali Bank, Dhaka"),
                ("10102", "2024-2025", 2024, 2025, "Dec 2024", "CH-2024-103", "15/12/2024", 7500.0, 90000.0, "Sonali Bank, Dhaka"),
                ("10100", "2025-2026", 2025, 2026, "Dec 2025", "CH-2025-101", "15/12/2025", 6000.0, 72000.0, "Sonali Bank, Dhaka"),
                ("10101", "2025-2026", 2025, 2026, "Dec 2025", "CH-2025-102", "15/12/2025", 4200.0, 50400.0, "Sonali Bank, Dhaka"),
                ("10102", "2025-2026", 2025, 2026, "Dec 2025", "CH-2025-103", "15/12/2025", 8200.0, 98400.0, "Sonali Bank, Dhaka")
            ]
            cursor.executemany("""
                INSERT INTO tax_records (
                    pin, fiscal_year, start_year, end_year, month, challan_no, challan_date, claim_amount, total_challan_amount, bank_info
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, sample_tax)

            cursor.execute("""
                INSERT OR IGNORE INTO dataset_batches (batch_id, fiscal_year, dataset_type, filename, record_count, file_size_bytes, uploaded_by)
                VALUES ('SAMPLE-DB-2425', '2024-2025', 'database', 'sample_database_2024_2025.csv', 4, 1024, 'system'),
                       ('SAMPLE-DB-2526', '2025-2026', 'database', 'sample_database_2025_2026.csv', 4, 1024, 'system'),
                       ('SAMPLE-TX-2425', '2024-2025', 'tax', 'sample_tax_2024_2025.csv', 3, 512, 'system'),
                       ('SAMPLE-TX-2526', '2025-2026', 'tax', 'sample_tax_2025_2026.csv', 3, 512, 'system')
            """)

        conn.commit()


def record_dataset_batch(fiscal_year: str, dataset_type: str, filename: str, record_count: int, file_size_bytes: int = 0, uploaded_by: str = "admin") -> str:
    init_db()
    batch_id = str(uuid.uuid4())[:12]
    with get_connection() as conn:
        cursor = conn.cursor()
        # Remove previous batch record for this fiscal year and type if exists
        cursor.execute("""
        DELETE FROM dataset_batches WHERE fiscal_year = ? AND dataset_type = ?
        """, (fiscal_year, dataset_type))

        cursor.execute("""
        INSERT INTO dataset_batches (batch_id, fiscal_year, dataset_type, filename, record_count, file_size_bytes, uploaded_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (batch_id, fiscal_year, dataset_type, filename, record_count, file_size_bytes, uploaded_by))
        conn.commit()
    return batch_id


def save_employees(employees: Dict[str, Employee], default_fiscal_year: Optional[str] = None, filename: str = "database.csv", uploaded_by: str = "admin"):
    init_db()
    if not employees:
        return

    sample_emp = next(iter(employees.values()))
    s_yr = getattr(sample_emp, 'start_year', 2025) or 2025
    e_yr = getattr(sample_emp, 'end_year', 2026) or (s_yr + 1)
    fy = default_fiscal_year or f"{s_yr}-{e_yr}"

    with get_connection() as conn:
        cursor = conn.cursor()
        for pin, emp in employees.items():
            s = getattr(emp, 'start_year', s_yr) or s_yr
            e = getattr(emp, 'end_year', e_yr) or e_yr
            salary_json = json.dumps(emp.monthly_salary)

            cursor.execute("""
            INSERT INTO employees (
                pin, fiscal_year, start_year, end_year, name, designation, department,
                gender, tin, monthly_salary, festival_bonus, arrears, others, gross, net_total
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(pin, fiscal_year) DO UPDATE SET
                start_year = excluded.start_year,
                end_year = excluded.end_year,
                name = excluded.name,
                designation = excluded.designation,
                department = excluded.department,
                gender = excluded.gender,
                tin = excluded.tin,
                monthly_salary = excluded.monthly_salary,
                festival_bonus = excluded.festival_bonus,
                arrears = excluded.arrears,
                others = excluded.others,
                gross = excluded.gross,
                net_total = excluded.net_total,
                created_at = CURRENT_TIMESTAMP
            """, (
                emp.pin, fy, s, e, emp.name, emp.designation, emp.department,
                emp.gender, emp.tin, salary_json, emp.festival_bonus, emp.arrears,
                emp.others, emp.gross, emp.net_total
            ))
        conn.commit()

    record_dataset_batch(fy, "database", filename, len(employees), uploaded_by=uploaded_by)


def save_tax_records(tax_records: Dict[str, List[TaxRecord]], default_fiscal_year: Optional[str] = None, filename: str = "tax.csv", uploaded_by: str = "admin"):
    init_db()
    if not tax_records:
        return

    fy = default_fiscal_year or "2025-2026"
    try:
        parts = fy.split("-")
        s_yr, e_yr = int(parts[0]), int(parts[1])
    except Exception:
        s_yr, e_yr = 2025, 2026

    total_recs = 0
    with get_connection() as conn:
        cursor = conn.cursor()
        # Delete old tax records for this fiscal year before saving new ones
        cursor.execute("DELETE FROM tax_records WHERE fiscal_year = ?", (fy,))

        for pin, rec_list in tax_records.items():
            for rec in rec_list:
                total_recs += 1
                cursor.execute("""
                INSERT INTO tax_records (
                    pin, fiscal_year, start_year, end_year, month, challan_no,
                    challan_date, claim_amount, total_challan_amount, bank_info
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rec.pin, fy, s_yr, e_yr, rec.month, rec.challan_no,
                    rec.challan_date, rec.claim_amount, rec.total_challan_amount, rec.bank_info
                ))
        conn.commit()

    record_dataset_batch(fy, "tax", filename, total_recs, uploaded_by=uploaded_by)


def get_fiscal_years() -> List[str]:
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT DISTINCT fiscal_year FROM employees
        UNION
        SELECT DISTINCT fiscal_year FROM tax_records
        ORDER BY fiscal_year DESC
        """)
        rows = cursor.fetchall()
        return [r[0] for r in rows if r[0]]


def get_all_dataset_batches() -> List[dict]:
    init_db()
    fys = get_fiscal_years()
    datasets = []

    with get_connection() as conn:
        cursor = conn.cursor()
        for fy in fys:
            # Employee Count
            cursor.execute("SELECT COUNT(*) FROM employees WHERE fiscal_year = ?", (fy,))
            emp_cnt = cursor.fetchone()[0]

            # Tax records count & total claim
            cursor.execute("SELECT COUNT(*), SUM(claim_amount) FROM tax_records WHERE fiscal_year = ?", (fy,))
            row_tax = cursor.fetchone()
            tax_cnt = row_tax[0] or 0
            tax_claim_tot = row_tax[1] or 0.0

            # Batches metadata
            cursor.execute("SELECT * FROM dataset_batches WHERE fiscal_year = ?", (fy,))
            batch_rows = cursor.fetchall()

            db_info = None
            tax_info = None
            for b in batch_rows:
                b_dict = {
                    "batch_id": b["batch_id"],
                    "filename": b["filename"],
                    "record_count": b["record_count"],
                    "file_size_bytes": b["file_size_bytes"],
                    "uploaded_by": b["uploaded_by"],
                    "created_at": b["created_at"],
                }
                if b["dataset_type"] == "database":
                    db_info = b_dict
                elif b["dataset_type"] == "tax":
                    tax_info = b_dict

            status = "complete" if (emp_cnt > 0 and tax_cnt > 0) else ("salary_only" if emp_cnt > 0 else "tax_only")

            datasets.append({
                "fiscal_year": fy,
                "status": status,
                "employee_count": emp_cnt,
                "tax_records_count": tax_cnt,
                "total_tax_claimed": tax_claim_tot,
                "database_batch": db_info,
                "tax_batch": tax_info,
            })

    return datasets


def load_employees(fiscal_year: Optional[str] = None) -> Dict[str, Employee]:
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        if fiscal_year and fiscal_year.lower() != 'all':
            cursor.execute("SELECT * FROM employees WHERE fiscal_year = ? ORDER BY id ASC", (fiscal_year,))
        else:
            cursor.execute("SELECT * FROM employees ORDER BY id ASC")

        rows = cursor.fetchall()
        employees: Dict[str, Employee] = {}
        for r in rows:
            monthly = json.loads(r["monthly_salary"]) if r["monthly_salary"] else [0.0] * 12
            emp = Employee(
                pin=r["pin"],
                gender=r["gender"] or "",
                tin=r["tin"] or "",
                name=r["name"] or "",
                designation=r["designation"] or "",
                department=r["department"] or "BRAC IED",
                monthly_salary=monthly,
                festival_bonus=r["festival_bonus"] or 0.0,
                arrears=r["arrears"] or 0.0,
                others=r["others"] or 0.0,
                start_year=r["start_year"] or 2025,
                end_year=r["end_year"] or 2026,
            )
            employees[r["pin"]] = emp
        return employees


def load_tax_records(fiscal_year: Optional[str] = None) -> Dict[str, List[TaxRecord]]:
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        if fiscal_year and fiscal_year.lower() != 'all':
            cursor.execute("SELECT * FROM tax_records WHERE fiscal_year = ? ORDER BY id ASC", (fiscal_year,))
        else:
            cursor.execute("SELECT * FROM tax_records ORDER BY id ASC")

        rows = cursor.fetchall()
        tax_store: Dict[str, List[TaxRecord]] = {}
        for r in rows:
            rec = TaxRecord(
                pin=r["pin"],
                month=r["month"] or "",
                challan_no=r["challan_no"] or "",
                challan_date=r["challan_date"] or "",
                claim_amount=r["claim_amount"] or 0.0,
                total_challan_amount=r["total_challan_amount"] or 0.0,
                bank_info=r["bank_info"] or "-",
            )
            tax_store.setdefault(r["pin"], []).append(rec)
        return tax_store


def delete_batch(batch_id: str):
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dataset_batches WHERE batch_id = ?", (batch_id,))
        batch = cursor.fetchone()
        if not batch:
            return False

        fy = batch["fiscal_year"]
        dtype = batch["dataset_type"]

        if dtype == "database":
            cursor.execute("DELETE FROM employees WHERE fiscal_year = ?", (fy,))
        elif dtype == "tax":
            cursor.execute("DELETE FROM tax_records WHERE fiscal_year = ?", (fy,))

        cursor.execute("DELETE FROM dataset_batches WHERE batch_id = ?", (batch_id,))
        conn.commit()
        return True


def delete_fiscal_year(fiscal_year: str):
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        if fiscal_year.lower() == 'all':
            cursor.execute("DELETE FROM employees")
            cursor.execute("DELETE FROM tax_records")
            cursor.execute("DELETE FROM dataset_batches")
        else:
            cursor.execute("DELETE FROM employees WHERE fiscal_year = ?", (fiscal_year,))
            cursor.execute("DELETE FROM tax_records WHERE fiscal_year = ?", (fiscal_year,))
            cursor.execute("DELETE FROM dataset_batches WHERE fiscal_year = ?", (fiscal_year,))
        conn.commit()


def clear_all_data():
    delete_fiscal_year('all')


def update_employee_tin(pin: str, fiscal_year: Optional[str] = None, new_tin: Optional[str] = None, new_name: Optional[str] = None, new_designation: Optional[str] = None):
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        updates = []
        params = []
        if new_tin is not None:
            updates.append("tin = ?")
            params.append(new_tin.strip())
        if new_name is not None:
            updates.append("name = ?")
            params.append(new_name.strip())
        if new_designation is not None:
            updates.append("designation = ?")
            params.append(new_designation.strip())

        if not updates:
            return False

        if fiscal_year and fiscal_year.lower() != 'all':
            sql = f"UPDATE employees SET {', '.join(updates)} WHERE pin = ? AND fiscal_year = ?"
            params.extend([pin.strip(), fiscal_year.strip()])
        else:
            sql = f"UPDATE employees SET {', '.join(updates)} WHERE pin = ?"
            params.append(pin.strip())

        cursor.execute(sql, params)
        conn.commit()
        return cursor.rowcount > 0


def create_tax_request(name: str, email: str, fiscal_year: str, designation: Optional[str] = None, tin: Optional[str] = None, remarks: Optional[str] = None, pin: Optional[str] = None) -> dict:
    init_db()
    req_id = f"REQ-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    assigned_pin = (pin or 'PENDING_PIN').strip()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tax_requests (req_id, pin, name, designation, tin, email, fiscal_year, remarks, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending')
        """, (req_id, assigned_pin, name.strip(), (designation or '').strip(), (tin or '').strip(), email.strip().lower(), fiscal_year.strip(), (remarks or '').strip()))
        conn.commit()
    return get_tax_request_by_req_id(req_id)


def update_tax_request_pin(req_id: str, pin: str) -> Optional[dict]:
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE tax_requests SET pin = ?, updated_at = CURRENT_TIMESTAMP WHERE req_id = ?", (pin.strip(), req_id.strip()))
        conn.commit()
    return get_tax_request_by_req_id(req_id)


def get_tax_requests(fiscal_year: Optional[str] = None, status: Optional[str] = None) -> List[dict]:
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM tax_requests"
        conditions = []
        params = []
        if fiscal_year and fiscal_year.lower() != 'all':
            conditions.append("fiscal_year = ?")
            params.append(fiscal_year.strip())
        if status and status.lower() != 'all':
            conditions.append("status = ?")
            params.append(status.strip())
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def get_tax_request_by_req_id(req_id: str) -> Optional[dict]:
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tax_requests WHERE req_id = ? OR pin = ? ORDER BY created_at DESC LIMIT 1", (req_id.strip(), req_id.strip()))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_tax_request_status(req_id: str, status: str, hr_notes: Optional[str] = None, prepared_by: Optional[str] = None) -> Optional[dict]:
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        updates = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
        params = [status.strip()]
        if hr_notes is not None:
            updates.append("hr_notes = ?")
            params.append(hr_notes.strip())
        if prepared_by is not None:
            updates.append("prepared_by = ?")
            params.append(prepared_by.strip())
        params.append(req_id.strip())
        cursor.execute(f"UPDATE tax_requests SET {', '.join(updates)} WHERE req_id = ?", params)
        conn.commit()
    return get_tax_request_by_req_id(req_id)
