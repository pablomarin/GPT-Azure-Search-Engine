#!/bin/bash
# Created by Mike Olivera
# https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/install-microsoft-odbc-driver-sql-server-macos?view=sql-server-ver16

# Check if Homebrew is installed
if command -v brew &>/dev/null; then
    echo "Homebrew is already installed."
else
    echo "Homebrew is not installed. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install.sh)"

    # Check if Homebrew was installed successfully
    if command -v brew &>/dev/null; then
        echo "Homebrew was installed successfully."
    else
        echo "Failed to install Homebrew."
    fi
fi

# Install ODBC Driver 17 for SQL Server
brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
brew update
brew install msodbcsql@13.1.9.2 mssql-tools@14.0.6.0