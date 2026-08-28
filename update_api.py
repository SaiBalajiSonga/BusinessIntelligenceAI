import re
with open('web/src/api.ts', 'r', encoding='utf-8') as f:
    code = f.read()

cache_code = '''
const cache = new Map<string, { data: any, time: number }>();
const CACHE_TTL = 30000; // 30s cache

async function fetchWithCache(url: string, init?: RequestInit) {
  if (!init || init.method === "GET" || init.method === undefined) {
    const cached = cache.get(url);
    if (cached && Date.now() - cached.time < CACHE_TTL) {
      return cached.data;
    }
  }
  
  const res = await fetch(url, init);
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || res.statusText);
  }
  const data = await res.json();
  
  if (!init || init.method === "GET" || init.method === undefined) {
    cache.set(url, { data, time: Date.now() });
  }
  return data;
}
'''

code = code.replace('async function apiFetch(path: string, init?: RequestInit) {\n  const res = await fetch(${API_BASE}, init);\n  if (!res.ok) {\n    const err = await res.text();\n    throw new Error(err || res.statusText);\n  }\n  return res.json();\n}', cache_code.strip() + '\n\nasync function apiFetch(path: string, init?: RequestInit) {\n  return fetchWithCache(${API_BASE}, init);\n}')

with open('web/src/api.ts', 'w', encoding='utf-8') as f:
    f.write(code)
