# WiFi Billing System - Setup & Usage Guide

## Installation

1.  **Environment Setup**: A virtual environment has been created in `venv`.
2.  **Dependencies**: Dependencies have been installed.
    *(If you need to reinstall for any reason):*
    ```powershell
    .\venv\Scripts\python.exe -m pip install -r requirements.txt
    ```

3.  **Run the Application**:
    To start the server, run this command in your terminal:
    ```powershell
    .\venv\Scripts\python.exe app.py
    ```

4.  **Access the Website**:
    Open your browser and navigate to: `http://127.0.0.1:5000`

## Features & Usage

### 1. Customer Flow
-   **Select Package**: Choose from detailed internet packages.
-   **Payment**: Enter M-PESA phone number.
    -   *Note*: The system is in **Sandbox Mode**. You must use test credentials or a whitelisted test phone number if available. STK Push will trigger, but callbacks require a public URL (ngrok).
-   **Success**: Upon successful payment simulation (or actual callback), an **Access Code** is generated.

### 2. Admin Dashboard
-   **Login URL**: `http://127.0.0.1:5000/admin`
-   **Credentials**:
    -   Username: `admin`
    -   Password: `admin123`
-   **Features**: View all transactions, filter by status, and export to CSV.

### 3. M-PESA Notes
-   The system uses Safaricom Sandbox.
-   **Callbacks**: To receive the "Payment Successful" update automatically, your local server must be accessible from the internet.
-   **Workaround**: You can view the `mpesa.py` file to see the integration logic.

## Project Structure
-   `app.py`: Main Flask application.
-   `mpesa.py`: M-PESA API integration.
-   `templates/`: HTML pages (neon themed).
-   `static/`: CSS and JS files.
-   `wifi_billing.db`: SQLite database (created on first run).
