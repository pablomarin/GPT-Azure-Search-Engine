#!/bin/bash

# Update this list to include the versions of Ubuntu you want to support
SUPPORTED_VERSIONS="18.04 20.04 22.04 24.04"

if ! [[ "$SUPPORTED_VERSIONS" == *"$(lsb_release -rs)"* ]];
then
    echo "Ubuntu $(lsb_release -rs) is not currently supported.";
    exit;
fi

echo "Downloading..."
curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list > /etc/apt/sources.list.d/mssql-release.list

echo "Updating apt-get..."
apt-get update

# Update the package names as per the available versions
echo "Installing msodbcsql..."
ACCEPT_EULA=Y apt-get install -y msodbcsql18 # Update this to the correct version
# optional: for bcp and sqlcmd
ACCEPT_EULA=Y apt-get install -y mssql-tools # Ensure the version matches the installed msodbcsql
echo 'export PATH="$PATH:/opt/mssql-tools/bin"' >> ~/.bashrc # Update PATH if the version of mssql-tools has changed
source ~/.bashrc
# optional: for unixODBC development headers
apt-get install -y unixodbc-dev

echo "DONE"