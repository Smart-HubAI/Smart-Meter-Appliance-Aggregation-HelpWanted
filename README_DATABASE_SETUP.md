# Database Setup and Running the Application

This guide explains how to prepare the PostgreSQL database and run this project on another computer.

## 1. Restore the PostgreSQL Database

If you have a backup file named `postgresql_backup_database.sql`, you can restore it to your local PostgreSQL installation.

First, create a new empty database. You can do this using `psql` or a tool like pgAdmin:
```bash
createdb -U postgres tata_power_nilm
```

Then, restore the SQL backup file into your new database:
```bash
psql -U postgres -d tata_power_nilm -f postgresql_backup_database.sql
```
*(You may be prompted to enter your PostgreSQL user password.)*

## 2. Update the `.env` File

This project reads its database configuration from a `.env` file in the root directory.

Open the `.env` file and find or add the `DATABASE_URL` variable. Update it with your PostgreSQL credentials:

```env
DATABASE_URL=postgresql://<USERNAME>:<PASSWORD>@<HOST>:<PORT>/<DATABASE_NAME>
```

Example:
```env
DATABASE_URL=postgresql://postgres:mysecretpassword@localhost:5432/tata_power_nilm
```

## 3. Install the Requirements

Ensure you have Python installed, then create and activate a virtual environment (recommended):

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

Next, install all required dependencies:
```bash
pip install -r requirements.txt
```

## 4. Run the Application

Once the database is set up and the dependencies are installed, you can start the application:

```bash
python app.py
```
The application will start and connect to the PostgreSQL database using the credentials specified in your `.env` file.
