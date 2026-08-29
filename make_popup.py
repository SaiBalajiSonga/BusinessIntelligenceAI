import re
with open('web/src/components/InlineFeedback.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

# Add position relative to the main container
code = code.replace('<div style={{ display: "flex", flexDirection: "column", gap: 12, alignItems: "flex-start" }}>', 
                    '<div style={{ display: "flex", flexDirection: "column", gap: 12, alignItems: "flex-end", position: "relative" }}>')

# Modify the disliking menu to be a popup
old_dislike = '''      {state === "disliking" && (
        <div style={{ 
          background: "var(--surface)", 
          border: "1px solid var(--border)", 
          borderRadius: "var(--radius-lg)", 
          padding: "16px",
          width: "100%",
          maxWidth: 420,
          boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
          animation: "slideDown 0.2s ease-out"
        }}>'''

new_dislike = '''      {state === "disliking" && (
        <div style={{ 
          position: "absolute",
          bottom: "100%",
          right: 0,
          marginBottom: 12,
          zIndex: 50,
          background: "var(--surface)", 
          border: "1px solid var(--border)", 
          borderRadius: "var(--radius-lg)", 
          padding: "16px",
          width: 320,
          boxShadow: "0 12px 24px rgba(0,0,0,0.15)",
          animation: "slideUp 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275)"
        }}>'''

code = code.replace(old_dislike, new_dislike)

with open('web/src/components/InlineFeedback.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
