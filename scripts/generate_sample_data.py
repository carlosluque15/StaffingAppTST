#!/usr/bin/env python3
"""Genera Staff.csv y Assignments.csv con datos INVENTADOS.

Mantiene exactamente las mismas columnas que las exportaciones reales de
SharePoint (para que ``import_staffing_csvs`` y la aplicacion funcionen igual),
pero no contiene ningun dato real: nombres, ids, correos, clientes y proyectos
son ficticios. Es determinista (misma --seed, mismo resultado) salvo por las
fechas, que se calculan respecto a --today.

Uso:
    python scripts/generate_sample_data.py --out backend/sample-data
"""

import argparse
import csv
import random
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

STAFF_COLUMNS = [
    "Title", "Picture", "Accenture Id", "Cloud First?", "Career Level Group",
    "Deployment City", "Deployment Country", "Pre-Defined Client",
    "Organization Unit", "Name", "Surname", "Career Track", "Career Counselor",
    "Role", "Sub-alignment", "Email", "Resource FTE", "Talent Segment",
    "Industry", "Revisar", "Responsible", "Considered for Time Report",
    "Curriculum Vitae", "isDeleted", "isDeletedText",
]
ASSIGNMENT_COLUMNS = [
    "Resource", "Project", "Project_new", "Client", "Industry", "Sold",
    "Starting Date", "Finishing Date", "Confirmed end", "Responsible",
    "% Assignment", "Created By", "Modified By", "Modified", "Comments", "ID",
    "Created",
]

FIRST_NAMES = [
    "Alba", "Alejandro", "Andrea", "Aitor", "Beatriz", "Bruno", "Carla", "Daniel",
    "Diana", "Eduardo", "Elena", "Emilio", "Fernando", "Gema", "Hugo", "Irene",
    "Ivan", "Jaime", "Julia", "Laura", "Leo", "Lucia", "Marcos", "Marta", "Mateo",
    "Nerea", "Nuria", "Oscar", "Paula", "Pablo", "Raul", "Rocio", "Sara", "Sergio",
    "Silvia", "Tomas", "Valeria", "Victor", "Xavier", "Yolanda",
]
SURNAMES = [
    "Almeida", "Barrios", "Calvo", "Dominguez", "Escudero", "Fuentes", "Galvez",
    "Herrera", "Iglesias", "Jurado", "Lorenzo", "Maldonado", "Navarro", "Ordonez",
    "Pardo", "Quintana", "Rivas", "Sandoval", "Tejada", "Urbano", "Vidal",
    "Yanez", "Zamora", "Aguado", "Bermejo", "Cuesta", "Duran", "Esteban",
    "Frutos", "Granados",
]

# (nivel, peso, sufijo de rol)
LEVELS = [
    ("Analyst", 38, "Analyst"),
    ("Consultant", 25, "Consultant"),
    ("Manager", 22, "Manager"),
    ("Senior Manager", 8, "Senior Manager"),
    ("Associate Director", 5, "Associate Director"),
    ("Accenture Leadership", 2, None),
]
SENIOR_LEVELS = {"Manager", "Senior Manager", "Associate Director", "Accenture Leadership"}
ROLE_TRACKS = [
    "Transformation Excellence", "Cloud Advisory", "Enterprise Architect",
    "Technology Strategy",
]
# Valores del catalogo real (taxonomia de negocio, no datos personales).
ORG_UNITS = [
    ("Tech Advisory", 46),
    ("Industry Tech Strategy & Enterprise Arch", 14),
    ("Digital Foundations", 12),
    ("Strategic Technology Effectiveness", 10),
    ("Technology Transformation Delivery", 9),
    ("Tech Strategy", 6),
    ("Technology Strategy & Transformation", 3),
]
CITIES = [("Madrid", 75), ("Barcelona", 22), ("Bilbao", 2), ("Sevilla", 1)]
TALENT_SEGMENTS = [
    ("Business & Technology Integration", 57), ("Advisory", 24), ("Strategy", 14),
    ("Empty", 5),
]
SUB_ALIGNMENTS = [
    ("Technology Transformation", 48), ("Cloud Advisory", 15),
    ("Technology Strategy", 13), ("Business Advisory", 6), ("", 8), ("Empty", 7),
    ("Business & Technology Delivery", 2), ("Business Strategy", 1),
]
INDUSTRIES = [
    "Financial Services", "Products", "Technology Strategy",
    "Communications, Media & Technology", "Health & Public Services", "Resources",
]
STAFF_INDUSTRY_WEIGHTS = [
    ("", 58), ("Financial Services", 24), ("Products", 8), ("Technology Strategy", 4),
    ("Communications, Media & Technology", 4), ("Health & Public Services", 2),
]

# Clientes totalmente inventados, cada uno con su industria.
CLIENTS = [
    ("Banco Meridiano", "Financial Services"),
    ("Aseguradora Cantabrico", "Financial Services"),
    ("Caja Rural del Sur Demo", "Financial Services"),
    ("Fintech Lumen", "Financial Services"),
    ("Gestora Atalaya", "Financial Services"),
    ("Bodegas Tramontana", "Products"),
    ("Retail Horizonte", "Products"),
    ("Automocion Pirineos", "Products"),
    ("Alimentos Solana", "Products"),
    ("Energia Aurora", "Resources"),
    ("Aguas del Levante Demo", "Resources"),
    ("Telecom Alisios", "Communications, Media & Technology"),
    ("Medios Ribera", "Communications, Media & Technology"),
    ("Hospital Universitario Demo", "Health & Public Services"),
    ("Ministerio de Pruebas", "Health & Public Services"),
    ("Consultora Interna Tech", "Technology Strategy"),
]
PROJECT_WORDS_A = [
    "Atlas", "Boreal", "Cenit", "Delta", "Eclipse", "Faro", "Geminis", "Helios",
    "Icaro", "Jupiter", "Kepler", "Lince", "Mistral", "Nebula", "Orion", "Polaris",
]
PROJECT_WORDS_B = [
    "Migracion Cloud", "Arquitectura Objetivo", "Estrategia Tecnologica",
    "Transformacion Digital", "Modernizacion Core", "Plan Director IT",
    "Gobierno del Dato", "Oficina de Transformacion", "Evaluacion de Plataformas",
]
SAMPLE_COMMENTS = [
    "Ampliacion pendiente de confirmar",
    "Reduccion de dedicacion acordada con el cliente",
    "Incorporacion tras vacaciones",
    "Asignacion provisional",
]


def weighted(rng, options):
    values, weights = zip(*[(o[0], o[1]) for o in options])
    return rng.choices(values, weights=weights, k=1)[0]


def ascii_id(text):
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c)).lower()


def fmt_date(d):
    return f"{d.month}/{d.day}/{d.year}"


def fmt_stamp(d, rng):
    hour = rng.randint(1, 12)
    return f"{d.month}/{d.day}/{d.year} {hour}:{rng.randint(0, 59):02d} {rng.choice(['AM', 'PM'])}"


def build_staff(rng, total):
    pairs = [(f, s) for f in FIRST_NAMES for s in SURNAMES]
    rng.shuffle(pairs)
    pairs = pairs[:total]
    level_options = [(name, weight) for name, weight, _ in LEVELS]
    people = []
    for first, surname in pairs:
        level = weighted(rng, level_options)
        people.append({
            "first": first,
            "surname": surname,
            "id": f"{ascii_id(first)}.{ascii_id(surname)}",
            "level": level,
            "deleted": rng.random() < 0.30,
        })
    seniors = [p for p in people if p["level"] in SENIOR_LEVELS and not p["deleted"]]
    if not seniors:  # garantiza responsables validos
        seniors = [p for p in people if not p["deleted"]][:3]

    rows = []
    for index, person in enumerate(people):
        level = person["level"]
        suffix = next(s for n, _, s in LEVELS if n == level)
        track = rng.choice(ROLE_TRACKS)
        role = f"{track} {suffix}" if suffix else "Managing Director"
        counselor = rng.choice([s for s in seniors if s["id"] != person["id"]])
        pre_client = rng.choices(
            ["", "Empty"] + [c[0] for c in CLIENTS[:4]], weights=[60, 9, 8, 8, 8, 7]
        )[0]
        deleted = person["deleted"]
        fte = rng.choices(["1", "0.6", "0.9", "0.7"], weights=[96, 2, 1, 1])[0]
        rows.append({
            "Title": f"{person['first']} {person['surname']}",
            "Picture": (
                f"https://example.com/pictures/{person['id']}.jpg"
                if rng.random() < 0.4 else ""
            ),
            "Accenture Id": person["id"],
            "Cloud First?": "True" if rng.random() < 0.07 else "False",
            "Career Level Group": level,
            "Deployment City": weighted(rng, CITIES),
            "Deployment Country": "Spain",
            "Pre-Defined Client": pre_client,
            "Organization Unit": weighted(rng, ORG_UNITS),
            "Name": person["first"],
            "Surname": person["surname"],
            "Career Track": "Client & Market",
            "Career Counselor": counselor["id"],
            "Role": role,
            "Sub-alignment": weighted(rng, SUB_ALIGNMENTS),
            "Email": f"{person['id']}@example.com",
            "Resource FTE": fte,
            "Talent Segment": weighted(rng, TALENT_SEGMENTS),
            "Industry": weighted(rng, STAFF_INDUSTRY_WEIGHTS),
            "Revisar": "False",
            "Responsible": counselor["id"],
            "Considered for Time Report": "False" if rng.random() < 0.03 else "True",
            "Curriculum Vitae": "",
            "isDeleted": "True" if deleted else "False",
            "isDeletedText": "yes" if deleted else "no",
        })
    return people, seniors, rows


def build_assignments(rng, people, seniors, today):
    rows = []
    next_id = [1]

    def make(person, start, end, percent, sold=True, confirmed=False):
        client, industry = rng.choice(CLIENTS)
        code = f"{rng.choice(PROJECT_WORDS_A)} {rng.choice(PROJECT_WORDS_B)}"
        author = rng.choice(seniors)
        editor = rng.choice(seniors)
        created = start - timedelta(days=rng.randint(5, 90))
        modified = max(created, today - timedelta(days=rng.randint(0, 200)))
        rows.append({
            "Resource": person["id"],
            "Project": rng.choice(["", "", code.split()[0]]),
            "Project_new": code,
            "Client": client,
            "Industry": industry if rng.random() > 0.05 else "",
            "Sold": "True" if sold else "False",
            "Starting Date": fmt_date(start),
            "Finishing Date": fmt_date(end),
            "Confirmed end": "True" if confirmed else "False",
            "Responsible": rng.choice(seniors)["id"],
            "% Assignment": "" if percent is None else f"{percent}%",
            "Created By": f"{author['surname']} {author['first']}, {author['first'][0]}.",
            "Modified By": f"{editor['surname']} {editor['first']}, {editor['first'][0]}.",
            "Modified": fmt_stamp(modified, rng),
            "Comments": rng.choice(SAMPLE_COMMENTS) if rng.random() < 0.06 else "",
            "ID": None,  # se asigna al final, barajado
            "Created": fmt_stamp(created, rng),
        })

    for person in people:
        # Historico: proyectos ya terminados.
        cursor = today - timedelta(days=rng.randint(200, 900))
        for _ in range(rng.randint(1, 3)):
            start = cursor
            end = start + timedelta(days=rng.randint(60, 300))
            if end >= today - timedelta(days=15):
                break
            make(person, start, end, rng.choice([100, 100, 80, 50, 60, 40]),
                 confirmed=rng.random() < 0.9)
            cursor = end + timedelta(days=rng.randint(1, 40))

        if person["deleted"]:
            continue

        # Vigente: ~75% de la gente tiene asignaciones activas hoy.
        if rng.random() < 0.75:
            split = rng.choice([[100], [100], [100], [50, 50], [80, 20], [70, 30],
                                [60, 40], [50], [30], [25, 25, 50]])
            for percent in split:
                start = today - timedelta(days=rng.randint(10, 400))
                end = today + timedelta(days=rng.randint(20, 320))
                make(person, start, end, percent, sold=rng.random() > 0.04)
        # Futuro: algunos tienen algo ya reservado.
        if rng.random() < 0.25:
            start = today + timedelta(days=rng.randint(30, 200))
            make(person, start, start + timedelta(days=rng.randint(60, 250)),
                 rng.choice([100, 50, 80]), sold=rng.random() > 0.3)

    # Algun porcentaje vacio, como en la exportacion real.
    for row in rng.sample(rows, k=max(1, len(rows) // 90)):
        row["% Assignment"] = ""

    ids = list(range(1, len(rows) + 1))
    rng.shuffle(ids)
    for row, assignment_id in zip(rows, ids):
        row["ID"] = str(assignment_id)
    rng.shuffle(rows)
    return rows


def write_csv(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as target:
        writer = csv.DictWriter(target, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="backend/sample-data")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--staff", type=int, default=140, help="filas de Staff")
    parser.add_argument("--today", default=None, help="AAAA-MM-DD (por defecto, hoy)")
    args = parser.parse_args()

    today = datetime.strptime(args.today, "%Y-%m-%d").date() if args.today else date.today()
    rng = random.Random(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    people, seniors, staff_rows = build_staff(rng, args.staff)
    assignment_rows = build_assignments(rng, people, seniors, today)
    write_csv(out / "Staff.csv", STAFF_COLUMNS, staff_rows)
    write_csv(out / "Assignments.csv", ASSIGNMENT_COLUMNS, assignment_rows)
    active = sum(1 for p in people if not p["deleted"])
    print(
        f"{out}/Staff.csv: {len(staff_rows)} filas ({active} activas); "
        f"{out}/Assignments.csv: {len(assignment_rows)} filas."
    )


if __name__ == "__main__":
    main()
