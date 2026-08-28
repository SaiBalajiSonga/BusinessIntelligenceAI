import re
with open('web/src/api.ts', 'r', encoding='utf-8') as f:
    code = f.read()

new_api = '''
  submitFeedback: async (payload: any) => {
    return apiFetch(/v1/feedback, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  
  testIntegration: async (payload: any) => {
    return apiFetch(/v1/integrations/test, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
'''

code = code.replace('submitFeedback: async (payload: any) => {\n    return apiFetch(/v1/feedback, {\n      method: "POST",\n      headers: { "Content-Type": "application/json" },\n      body: JSON.stringify(payload),\n    });\n  },', new_api.strip())

with open('web/src/api.ts', 'w', encoding='utf-8') as f:
    f.write(code)
