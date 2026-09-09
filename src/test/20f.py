from edgar import *

set_identity("MIKG Research your.email@example.com")

c = Company("TSM")
d = c.data
print(d.name, "|", d.entity_type, "|", d.sic, "|", d.exchanges)

# 어떤 폼을 내는지 확인
fs = c.get_filings()
forms = {}
for f in fs.latest(50):
    forms[f.form] = forms.get(f.form, 0) + 1
print(forms)

