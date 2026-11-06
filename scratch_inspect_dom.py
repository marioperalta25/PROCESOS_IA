from bs4 import BeautifulSoup

with open('analisishumano/analisis.md', encoding='utf-8', errors='ignore') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

print("All elements with data-scope-id:")
for el in soup.select("[data-scope-id]"):
    print(el.name, el.get('class'), el.get('data-scope-id'))

print("\nAll elements with data-subtree:")
for el in soup.select("[data-subtree]"):
    print(el.name, el.get('class'), el.get('data-subtree'), repr(el.get_text()[:40]))

print("\nAll h3 elements:")
for el in soup.select("h3"):
    print(el.name, el.get('class'), repr(el.get_text()[:60]))
