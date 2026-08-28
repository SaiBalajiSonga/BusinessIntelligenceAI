import re
with open('api/main.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_endpoint = '''
class IntegrationCreds(BaseModel):
    engine: str
    host: str | None = None
    database: str | None = None
    user: str | None = None
    password: str | None = None

@app.post("/v1/integrations/test", tags=["system"])
async def test_integration(creds: IntegrationCreds) -> dict:
    import asyncio
    # Simulate network latency and introspection for demo purposes
    await asyncio.sleep(2.5)
    
    # In a real implementation, we would connect to PostgreSQL/Snowflake here
    # e.g., using psycopg2 or snowflake-connector-python
    
    if creds.engine == "postgresql" and creds.user == "fail":
        raise HTTPException(401, "Authentication failed for user 'fail'")
        
    return {
        "status": "success",
        "message": f"Successfully connected to {creds.engine.title()}.",
        "schema_introspected": True,
        "tables_found": 14,
        "kpis_generated": 5
    }
'''

code += '\n' + new_endpoint

with open('api/main.py', 'w', encoding='utf-8') as f:
    f.write(code)
