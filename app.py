from flask import Flask, render_template, request, redirect, send_file
import sqlite3
import pandas as pd
from datetime import datetime
from datetime import datetime
from dateutil.relativedelta import relativedelta


def calculate_rd_monthly_values(start_year, start_month_name, start_value, maturity_date_str, increment):
    month_names = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']
    monthly_values = {}
    start_date = datetime(start_year, month_names.index(start_month_name) + 1, 1)
    end_date = datetime.strptime(maturity_date_str, "%Y-%m-%d")
    current_value = start_value

    while start_date <= end_date:
        m = start_date.strftime("%b").lower()
        y = start_date.year
        key = f"{y}-{m}"
        monthly_values[key] = current_value
        current_value += increment
        start_date += relativedelta(months=1)

    # ✅ Debug print — add this before return
    print("Generated RD values:")
    for k, v in monthly_values.items():
        print(f"{k}: {v}")

    return monthly_values




app = Flask(__name__)
DB = 'data.db'

def init_db():
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS investments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                investment_id INTEGER,
                reference_name TEXT,
                bank TEXT,
                account_type TEXT,
                saving_invested TEXT,
                status TEXT,
                year INTEGER,
                maturity_date TEXT,
                jan REAL, feb REAL, mar REAL, apr REAL, may REAL, jun REAL,
                jul REAL, aug REAL, sep REAL, oct REAL, nov REAL, dec REAL,
                notepad TEXT
            )
        ''')
        cursor.execute('''
    CREATE TABLE IF NOT EXISTS options (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,         
        value TEXT UNIQUE
    )
''')

init_db()

def safe_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0

def update_expired_statuses():
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE investments
            SET status = 'Closed'
            WHERE maturity_date IS NOT NULL
              AND maturity_date != ''
              AND maturity_date < DATE('now')
              AND status != 'Closed'
        ''')
        conn.commit()

def get_upcoming_maturities(limit=4):
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT reference_name, bank, account_type, MIN(maturity_date) AS earliest_date
            FROM investments
            WHERE maturity_date IS NOT NULL AND maturity_date != ''
              AND maturity_date >= DATE('now')
            GROUP BY reference_name
            ORDER BY earliest_date ASC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        formatted = []
        for r in rows:
            try:
                dt = pd.to_datetime(r[3])
                formatted_date = dt.strftime('%d%b%y')
            except:
                formatted_date = r[3]
            formatted.append((r[0], r[1], r[2], formatted_date))
        return formatted
    
    

@app.route("/update/<int:record_id>", methods=["GET", "POST"])
@app.route("/update/<int:id>", methods=["GET", "POST"])
def update(id):
    if request.method == "POST":
        try:
            reference_name = request.form["reference_name"]
            bank = request.form["bank"]
            account_type = request.form["account_type"]
            saving_invested = request.form["saving_invested"]
            status = request.form["status"]
            start_year = int(request.form["year"])
            notepad = request.form["notepad"]
            maturity_date_str = request.form.get("maturity_date", "")

            month_keys = ["jan", "feb", "mar", "apr", "may", "jun",
                          "jul", "aug", "sep", "oct", "nov", "dec"]
            raw_values = [request.form.get(m) for m in month_keys]
            month_values = [safe_float(v) for v in raw_values]

            with sqlite3.connect(DB) as conn:
                cursor = conn.cursor()

                if account_type == "RD":
                    
                    maturity_date = pd.to_datetime(maturity_date_str)
                    end_year = maturity_date.year

                    start_month_name = None
                    start_value = None
                    for m, v in zip(month_keys, month_values):
                        if v > 0:
                            start_month_name = m
                            start_value = v
                            break

                    if start_month_name and start_value:
                        increment = safe_float(request.form.get("rd_increment", "0"))
                        full_values = calculate_rd_monthly_values(start_year, start_month_name, start_value, maturity_date_str,increment)
                        with sqlite3.connect(DB) as conn:
                            cursor = conn.cursor()

                        # Delete old RD rows
                        cursor.execute("DELETE FROM investments WHERE investment_id=?", (id,))

                        # Insert updated RD rows
                       
                        for year in range(start_year, end_year + 1):
                            year_values = {m: 0 for m in month_keys}
                            has_data = False
                            
                            for m in month_keys:
                                key = f"{year}-{m}"
                                
                                
                                if key in full_values:
                                
                                    year_values[m] = full_values[key]
                                    has_data = True
                            if has_data:
                                data = (
                                    id, reference_name, bank, account_type, saving_invested, status,
                                    year, maturity_date_str,
                                    *[year_values[m] for m in month_keys], notepad
                            )
                            cursor.execute('''
                                INSERT INTO investments (
                                    investment_id, reference_name, bank, account_type, saving_invested, status,
                                    year, maturity_date,
                                    jan, feb, mar, apr, may, jun,
                                    jul, aug, sep, oct, nov, dec,
                                    notepad
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', data)
                else:
                    # Update single row for non-RD
                    cursor.execute('''
                        UPDATE investments SET
                            reference_name=?, bank=?, account_type=?, saving_invested=?, status=?, year=?, maturity_date=?,
                            jan=?, feb=?, mar=?, apr=?, may=?, jun=?,
                            jul=?, aug=?, sep=?, oct=?, nov=?, dec=?, notepad=?
                        WHERE investment_id=?
                    ''', (
                        reference_name, bank, account_type, saving_invested, status, start_year, maturity_date_str,
                        *month_values, notepad, id
                    ))

                conn.commit()
            return redirect("/")
        except Exception as e:
            return f"Update Error: {e}", 400

    # GET method: load all rows for this investment_id
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM investments WHERE investment_id=?", (id,))
        records = cursor.fetchall()

        # also fetch dynamic options
        cursor.execute("SELECT value FROM options WHERE type='bank' ORDER BY value")
        banks = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT value FROM options WHERE type='account_type' ORDER BY value")
        account_types = [row[0] for row in cursor.fetchall()]

    record = records[0] if records else None

    return render_template(
        "update.html",
        record=record,
        records=records,
        banks=banks,
        account_types=account_types
    )


@app.route("/delete_by_ref/<reference_name>")
def delete_by_ref(reference_name):
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM investments WHERE reference_name = ?", (reference_name,))
        conn.commit()
    return redirect("/")

@app.route("/", methods=["GET", "POST"])
@app.route("/", methods=["GET", "POST"])
def index():
    update_expired_statuses()

    if request.method == "POST":
        try:
            reference_name = request.form.get("reference_name") or f"INV-{int(datetime.now().timestamp())}"
            bank = request.form["bank"]
            account_type = request.form["account_type"]
            saving_invested = request.form["saving_invested"]
            status = request.form["status"]
            start_year = int(request.form["year"])
            notepad = request.form["notepad"]
            investment_id = int(datetime.now().timestamp())
            maturity_date_str = request.form.get("maturity_date", "")

            if account_type.lower() == "savings":
                status = "Open"

            month_keys = ["jan", "feb", "mar", "apr", "may", "jun",
                          "jul", "aug", "sep", "oct", "nov", "dec"]
            raw_values = [request.form.get(m) for m in month_keys]
            month_values = [safe_float(v) for v in raw_values]

            # --- RD multi-year insert logic ---
            if account_type == "RD":
                maturity_date = pd.to_datetime(maturity_date_str)
                end_year = maturity_date.year

                start_month_name = None
                start_value = None
                for m, v in zip(month_keys, month_values):
                    if v > 0:
                        start_month_name = m
                        start_value = v
                        break

                if start_month_name and start_value:
                    increment = safe_float(request.form.get("rd_increment", "0"))
                    full_values = calculate_rd_monthly_values(start_year, start_month_name, start_value, maturity_date_str,increment)

                    with sqlite3.connect(DB) as conn:
                        cursor = conn.cursor()
                        for year in range(start_year, end_year + 1):
                            year_values = {m: 0 for m in month_keys}
                            has_data = False
                            for m in month_keys:
                                
                                key = f"{year}-{m}"
                                if key in full_values:
        
                                    year_values[m] = full_values.get(key,0)

                                    has_data = True
                                    if has_data:
                                        data = (
                                            investment_id, reference_name, bank, account_type, saving_invested, status,
                                            year, maturity_date_str,
                                            *[year_values[m] for m in month_keys], notepad
                                        )
                            cursor.execute('''
                                INSERT INTO investments (
                                    investment_id, reference_name, bank, account_type, saving_invested, status,
                                    year, maturity_date,
                                    jan, feb, mar, apr, may, jun,
                                    jul, aug, sep, oct, nov, dec,
                                    notepad
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', data)
                    return redirect("/")

            # --- FD & NSC multi-year insert logic ---
            elif account_type in ["FD", "NSC"]:
                maturity_date = pd.to_datetime(maturity_date_str)
                end_year = maturity_date.year
                end_month = maturity_date.month

                start_month = None
                start_value = None
                for i, v in enumerate(month_values):
                    if v > 0:
                        start_month = i + 1
                        start_value = v
                        break

                if start_month and start_value is not None:
                    with sqlite3.connect(DB) as conn:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM investments WHERE reference_name=?", (reference_name,))
                        for year in range(start_year, end_year + 1):
                            year_values = {m: 0 for m in month_keys}
                            for i, m in enumerate(month_keys):
                                month_index = i + 1
                                if (year == start_year and month_index >= start_month) or \
                                   (year == end_year and month_index <= end_month) or \
                                   (start_year < year < end_year):
                                    year_values[m] = start_value

                            data = (
                                investment_id, reference_name, bank, account_type, saving_invested, status,
                                year, maturity_date_str,
                                *[year_values[m] for m in month_keys], notepad
                            )
                            cursor.execute('''
                                INSERT INTO investments (
                                    investment_id, reference_name, bank, account_type, saving_invested, status,
                                    year, maturity_date,
                                    jan, feb, mar, apr, may, jun,
                                    jul, aug, sep, oct, nov, dec,
                                    notepad
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', data)
                    return redirect("/")

            # --- Single-record insert for other account types ---
            with sqlite3.connect(DB) as conn:
                cursor = conn.cursor()
                data = (
                    investment_id, reference_name, bank, account_type, saving_invested, status,
                    start_year, maturity_date_str,
                    *month_values, notepad
                )
                cursor.execute('''
                    INSERT INTO investments (
                        investment_id, reference_name, bank, account_type, saving_invested, status,
                        year, maturity_date,
                        jan, feb, mar, apr, may, jun,
                        jul, aug, sep, oct, nov, dec,
                        notepad
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', data)
            return redirect("/")

        except Exception as e:
            return f"Error: {e}", 400

        # --- GET method: filter and display records ---
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM options WHERE type='bank' ORDER BY value")
        banks = [row[0] for row in cursor.fetchall()]

        cursor.execute("SELECT value FROM options WHERE type='account_type' ORDER BY value")
        account_types = [row[0] for row in cursor.fetchall()]

    filters = {
        "bank": request.args.get("bank", ""),
        "account_type": request.args.get("account_type", ""),
        "saving_invested": request.args.get("saving_invested", ""),
        "status": request.args.get("status", ""),
        "year": request.args.get("year", ""),
        "start_date": request.args.get("start_date", ""),
        "end_date": request.args.get("end_date", ""),
        "unique_only": request.args.get("unique_only", "")
    }

    rows = []   # ✅ default: no data
    monthly_totals = [0] * 12
    next_maturity = []

    # ✅ only run query if at least one filter is set
    if any(filters.values()):
        base_query = "SELECT * FROM investments WHERE 1=1"
        params = []

        for field, value in filters.items():
            if field in ["bank", "account_type", "saving_invested", "status", "year"] and value:
                base_query += f" AND {field} LIKE ?"
                params.append(f"%{value}%")
        if filters["start_date"]:
            base_query += " AND maturity_date >= ?"
            params.append(filters["start_date"])
        if filters["end_date"]:
            base_query += " AND maturity_date <= ?"
            params.append(filters["end_date"])

        if filters["unique_only"]:
            query = f"""
                SELECT * FROM (
                    {base_query}
                )
                WHERE id IN (
                    SELECT MIN(id)
                    FROM investments
                    GROUP BY reference_name
                )
                ORDER BY reference_name, year
            """
        else:
            query = base_query + " ORDER BY reference_name, year"

        with sqlite3.connect(DB) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        monthly_totals = [0] * 12
        for row in rows:
            for i in range(9, 21):
                monthly_totals[i - 9] += safe_float(row[i])

        next_maturity = get_upcoming_maturities()

    return render_template("index.html", records=rows, filters=filters,
                           monthly_totals=monthly_totals, next_maturity=next_maturity,
                           banks=banks, account_types=account_types)




@app.route("/dashboard")
def dashboard():
    with sqlite3.connect(DB) as conn:
        # Open Unique FD/RD/NSC Count
        df_open_unique = pd.read_sql_query("""
            SELECT bank, account_type, COUNT(DISTINCT reference_name) AS open_unique_count
            FROM investments
            WHERE account_type IN ('FD', 'RD', 'NSC')
              AND status = 'Open'
            GROUP BY bank, account_type
        """, conn)
# NEW: totals across all banks
        df_totals = pd.read_sql_query("""
            SELECT account_type, COUNT(DISTINCT reference_name) AS total_count
            FROM investments
            WHERE status = 'Open'
            GROUP BY account_type
        """, conn)
        # Savings totals by month, aggregated across all banks, grouped by year
        df_savings_monthly = pd.read_sql_query("""
            SELECT year,
                   COALESCE(SUM(jan),0) AS jan,
                   COALESCE(SUM(feb),0) AS feb,
                   COALESCE(SUM(mar),0) AS mar,
                   COALESCE(SUM(apr),0) AS apr,
                   COALESCE(SUM(may),0) AS may,
                   COALESCE(SUM(jun),0) AS jun,
                   COALESCE(SUM(jul),0) AS jul,
                   COALESCE(SUM(aug),0) AS aug,
                   COALESCE(SUM(sep),0) AS sep,
                   COALESCE(SUM(oct),0) AS oct,
                   COALESCE(SUM(nov),0) AS nov,
                   COALESCE(SUM(dec),0) AS dec
            FROM investments
            WHERE account_type = 'Savings'
            GROUP BY year
            ORDER BY year
        """, conn)

        # Invested totals by month, aggregated across all banks, grouped by year
        df_invested_monthly = pd.read_sql_query("""
            SELECT year,
                   COALESCE(SUM(jan),0) AS jan,
                   COALESCE(SUM(feb),0) AS feb,
                   COALESCE(SUM(mar),0) AS mar,
                   COALESCE(SUM(apr),0) AS apr,
                   COALESCE(SUM(may),0) AS may,
                   COALESCE(SUM(jun),0) AS jun,
                   COALESCE(SUM(jul),0) AS jul,
                   COALESCE(SUM(aug),0) AS aug,
                   COALESCE(SUM(sep),0) AS sep,
                   COALESCE(SUM(oct),0) AS oct,
                   COALESCE(SUM(nov),0) AS nov,
                   COALESCE(SUM(dec),0) AS dec
            FROM investments
            WHERE saving_invested = 'Invested'
            GROUP BY year
            ORDER BY year
        """, conn)

    return render_template(
        "dashboard.html",
        open_unique=df_open_unique.to_dict(orient="records"),
        savings_monthly=df_savings_monthly.fillna(0).to_dict(orient="records"),
        invested_monthly=df_invested_monthly.fillna(0).to_dict(orient="records"),
        totals=df_totals.to_dict(orient="records")
        
    )
@app.route("/export/<fmt>")
def export(fmt):
    with sqlite3.connect(DB) as conn:
        df = pd.read_sql_query("SELECT * FROM investments", conn)
        if fmt == "csv":
            df.to_csv("investments.csv", index=False)
            return send_file("investments.csv", as_attachment=True)
        elif fmt == "excel":
            df.to_excel("investments.xlsx", index=False)
            return send_file("investments.xlsx", as_attachment=True)
        
        
@app.route("/manage_options", methods=["GET", "POST"])
def manage_options():
    if request.method == "POST":
        new_type = request.form["type"]
        new_value = request.form["value"].strip()
        if new_type and new_value:
            with sqlite3.connect(DB) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO options (type, value) VALUES (?, ?)", (new_type, new_value))
                conn.commit()
        return redirect("/manage_options")

    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT type, value FROM options ORDER BY type, value")
        options = cursor.fetchall()

    return render_template("manage_options.html", options=options)


    
@app.route("/debug_options")
def debug_options():
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT type, value FROM options ORDER BY type, value")
        rows = cursor.fetchall()
    return "<br>".join([f"{t}: {v}" for t, v in rows])

@app.route("/delete_option/<option_type>/<option_value>")
def delete_option(option_type, option_value):
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM options WHERE type=? AND value=?", (option_type, option_value))
        conn.commit()
    return redirect("/manage_options")

@app.route("/bank_summary")
def bank_summary():
    with sqlite3.connect(DB) as conn:
        # Total Saving by Bank, Year, and Month
        df_saving = pd.read_sql_query("""
            SELECT bank, year,
                   SUM(jan + feb + mar + apr + may + jun + jul + aug + sep + oct + nov + dec) AS total_saving
            FROM investments
            WHERE saving_invested = 'Saving'
            GROUP BY bank, year
        """, conn)

        # Total Investment by Bank, Year, and Month
        df_invested = pd.read_sql_query("""
            SELECT bank, year,
                   SUM(jan + feb + mar + apr + may + jun + jul + aug + sep + oct + nov + dec) AS total_investment
            FROM investments
            WHERE saving_invested = 'Invested'
            GROUP BY bank, year
        """, conn)

        # Current month totals
        current_month = datetime.now().strftime("%b").lower()
        df_current = pd.read_sql_query(f"""
            SELECT bank, year,
                   SUM({current_month}) AS current_month_total
            FROM investments
            GROUP BY bank, year
        """, conn)

    return render_template(
        "bank_summary.html",
        saving_data=df_saving.to_dict(orient="records"),
        invested_data=df_invested.to_dict(orient="records"),
        current_data=df_current.to_dict(orient="records")
    )


if __name__ == "__main__":
    app.run(debug=True)
