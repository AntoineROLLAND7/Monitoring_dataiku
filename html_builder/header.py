# html_builder/header.py
# Génère le bandeau titre et le badge de date du dashboard


def build_header_html(date_str: str) -> str:
    """
    Retourne le HTML du header avec le titre et le badge de date.

    Args:
        date_str : Date formatée (ex: "April 14, 2025")
    """
    return f"""
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" />
<main>
    <div class="header-container">
        <div class="title-group">
            <h1>Project Quality Execution <span>Control Center</span></h1>
        </div>
        <div class="data-badge">
            <span class="pulse-dot"></span>
            Date: <span id="current-timestamp">{date_str}</span>
        </div>
    </div>
"""
