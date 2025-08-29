import os

def is_azure_deployment():
    """Detect if running in Azure App Service"""
    return (
        os.environ.get('WEBSITE_SITE_NAME') is not None or 
        os.environ.get('AZURE_CLIENT_ID') is not None or
        os.environ.get('WEBSITE_RESOURCE_GROUP') is not None
    )

def get_db_config():
    """Get database configuration based on environment"""
    if is_azure_deployment():
        # Azure production database
        return {
            'user': os.environ.get('DB_USER', 'hpkrhbkroa'),
            'password': os.environ.get('DB_PASSWORD', 'Resident20!)'),
            'host': os.environ.get('DB_HOST', 'planreview-server.postgres.database.azure.com'),
            'port': int(os.environ.get('DB_PORT', '5432')),
            'database': os.environ.get('DB_NAME', 'postgres')
        }
    else:
        # Local development database
        return {
            'user': os.environ.get('DB_USER', 'admin'),
            'password': os.environ.get('DB_PASSWORD', 'admin'),
            'host': os.environ.get('DB_HOST', '127.0.0.1'),
            'port': int(os.environ.get('DB_PORT', '54547')),
            'database': os.environ.get('DB_NAME', 'postgres')
        }