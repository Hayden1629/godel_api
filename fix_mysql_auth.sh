#!/bin/bash
# Fix MySQL authentication to allow password-based login
# This changes root from auth_socket to password authentication

echo "Fixing MySQL authentication..."
echo ""
echo "This will change root user to use password authentication (empty password for now)"
echo "You can set a password later if needed."
echo ""

# Run the SQL commands
sudo mysql <<EOF
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '';
FLUSH PRIVILEGES;
SELECT 'MySQL authentication fixed! Root user now uses password authentication.' AS Status;
EOF

echo ""
echo "✅ Done! You can now connect to MySQL with:"
echo "   User: root"
echo "   Password: (empty)"
echo ""
echo "Try running: python init_database.py"

