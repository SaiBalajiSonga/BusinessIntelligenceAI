import re
with open('web/src/pages/Integrations.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

# Add imports
code = code.replace('import Loader from "../components/Loader";', 'import Loader from "../components/Loader";\nimport { Cloud, Search, Database, Server, Component } from "lucide-react";')

# Replace CONNECTORS array
old_connectors = r'const CONNECTORS = \[.*?\];'
new_connectors = '''const CONNECTORS = [
  { id: "snowflake", name: "Snowflake", icon: <Cloud size={32} color="var(--brand)" />, desc: "Connect to your Snowflake Data Cloud" },
  { id: "bigquery", name: "Google BigQuery", icon: <Search size={32} color="#4285F4" />, desc: "Connect to your GCP Data Warehouse" },
  { id: "postgresql", name: "PostgreSQL", icon: <Database size={32} color="#336791" />, desc: "Connect to standard PostgreSQL databases" },
  { id: "redshift", name: "Amazon Redshift", icon: <Server size={32} color="#FF9900" />, desc: "Connect to your AWS Data Warehouse" },
  { id: "databricks", name: "Databricks", icon: <Component size={32} color="#FF3621" />, desc: "Connect to Databricks SQL or Spark" },
];'''

code = re.sub(old_connectors, new_connectors, code, flags=re.DOTALL)

with open('web/src/pages/Integrations.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
