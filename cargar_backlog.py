#!/usr/bin/env python3
"""
Carga el backlog del proyecto de encuestas en GitHub: etiquetas, 6 milestones
(uno por sprint) y 54 issues (ENC-001 a ENC-054).

Requisitos:
  - Python 3.9+ (solo biblioteca estándar)
  - GitHub CLI (gh) autenticado:  gh auth login
  - Para agregar al Project directamente: gh auth refresh -s project

Uso:
  # 1) Ver qué haría, sin tocar GitHub
  python3 cargar_backlog.py --repo usuario/encuestas --inicio 2026-10-19 --dry-run

  # 2) Cargar
  python3 cargar_backlog.py --repo usuario/encuestas --inicio 2026-10-19

  # Reescribir título y cuerpo de los issues que ya existen
  # (por ejemplo, para corregir acentos dañados en Windows)
  python3 cargar_backlog.py --repo usuario/encuestas --inicio 2026-10-19 --reparar

  # 3) Opcional: agregar cada issue a un Project (número y dueño del Project)
  python3 cargar_backlog.py --repo usuario/encuestas --inicio 2026-10-19 \
      --proyecto 3 --owner usuario

Es idempotente: si lo corres dos veces, no duplica etiquetas, milestones ni
issues (identifica cada issue por su prefijo ENC-0XX en el título).

Si el repo todavía no tiene issues ni PRs, ENC-00N queda como el issue #N.
"""

import argparse
import datetime as dt
import json
import subprocess
import sys

# ---------------------------------------------------------------------------
# Sprints: (número, título del milestone, días hábiles, hito)
# ---------------------------------------------------------------------------
SPRINTS = [
    (0, "Sprint 0 — Setup y esqueleto", 5,
     "Un hola mundo pasa por ticket, PR, CI, revisión y despliegue con HTTPS en Oracle."),
    (1, "Sprint 1 — Seguridad, organización y proveedores", 10,
     "Están completos los catálogos de los que dependen las campañas."),
    (2, "Sprint 2 — Preguntas y motor de campañas", 10,
     "Lanzar una quincena envía las invitaciones y el recordatorio sale solo."),
    (3, "Sprint 3 — Contestador, seguimiento y reportes", 10,
     "Se cumplen los procesos primarios del SOW."),
    (4, "Sprint 4 — Dashboard y modo demo", 10,
     "La demo completa se recorre en un par de minutos."),
    (5, "Sprint 5 — Endurecimiento y entrega", 9,
     "Listo para producción y para el portafolio. Incluye 2.5 días de holgura."),
]

# Días feriados oficiales en México dentro del periodo probable del proyecto.
FESTIVOS_DEFAULT = ["2026-11-16", "2026-12-25", "2027-01-01", "2027-02-01", "2027-03-15"]

# ---------------------------------------------------------------------------
# Etiquetas
# ---------------------------------------------------------------------------
MODULOS_APP = [
    "seguridad", "organizacion", "proveedores", "preguntas", "campanas",
    "contestador", "seguimiento", "reportes", "dashboard", "demo",
]

LABELS = {
    "front": ("1d76db", "Pantallas, GSP, CSS, JS"),
    "back": ("0e8a16", "Dominio, servicios, controladores, jobs"),
    "devops": ("5319e7", "Infraestructura, CI/CD, despliegue"),
    "docs": ("c5def5", "Documentación, ADRs, README"),
    "refinar": ("e99695", "Falta completar la plantilla antes de iniciar (Definition of Ready)"),
    "mod:infra": ("d4c5f9", "Infraestructura y setup"),
    "mod:docs": ("d4c5f9", "Documentación"),
}
for _m in MODULOS_APP:
    LABELS[f"mod:{_m}"] = ("fbca04", f"Módulo {_m}")


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------
def t(id_, sprint, modulo, tipos, dias, titulo, criterios, deps=()):
    return {
        "id": id_, "sprint": sprint, "modulo": modulo, "tipos": tipos,
        "dias": dias, "titulo": titulo, "criterios": criterios, "deps": list(deps),
    }


TICKETS = [
    # ---------------- Sprint 0 ----------------
    t("ENC-001", 0, "infra", ["devops"], 0.5,
      "Repo, ruleset de main, plantillas de PR e issue, etiquetas y Project",
      ["main exige PR y checks en verde, sin aprobaciones obligatorias",
       "Squash merge como única opción y force push prohibido",
       "Existen la plantilla de PR y la plantilla de issue del plan",
       "El Project tiene vistas de tablero, tabla y roadmap"]),
    t("ENC-002", 0, "docs", ["docs"], 0.25,
      "ADRs iniciales",
      ["ADR-0001 monolito Grails con GSP",
       "ADR-0002 correo detrás de un puerto (ServicioCorreo)",
       "ADR-0003 hosting en Oracle Always Free con Render como respaldo",
       "ADR-0004 migraciones con Liquibase",
       "ADR-0005 un mismo set de preguntas por quincena"],
      ["ENC-001"]),
    t("ENC-003", 0, "infra", ["back"], 0.5,
      "Esqueleto Grails 7 con Grails Forge, toolchain de Java en Gradle y paquetes por módulo",
      ["./gradlew bootRun levanta la app en una máquina limpia",
       "El JDK correcto se descarga solo vía toolchain de Gradle",
       "Existen los paquetes de los módulos de la app"],
      ["ENC-001"]),
    t("ENC-004", 0, "infra", ["devops"], 0.5,
      "compose.yaml con PostgreSQL y Mailpit, y .env.example",
      ["PostgreSQL usa un volumen con nombre y los datos sobreviven a down/up",
       "Mailpit se ve en el navegador y recibe correos de la app",
       ".env.example documenta todas las variables necesarias"],
      ["ENC-003"]),
    t("ENC-005", 0, "infra", ["back"], 0.5,
      "Liquibase con changelog inicial, Actuator /health y logs estructurados",
      ["El esquema se crea solo con Liquibase, sin dbCreate: update",
       "/actuator/health responde UP e incluye el estado de la base de datos",
       "Los logs salen en formato JSON"],
      ["ENC-004"]),
    t("ENC-006", 0, "infra", ["back"], 0.5,
      "Pruebas Spock unitarias y de integración con Testcontainers",
      ["Una prueba unitaria de Spock corre con ./gradlew test",
       "Una prueba de integración corre contra un PostgreSQL real en Testcontainers"],
      ["ENC-005"]),
    t("ENC-007", 0, "infra", ["devops"], 0.25,
      "Dockerfile multi-stage para amd64 y arm64",
      ["La imagen se construye para amd64 y arm64",
       "La imagen arranca y responde /actuator/health en ambas arquitecturas"],
      ["ENC-003"]),
    t("ENC-008", 0, "infra", ["devops"], 0.5,
      "CI de PR: build, pruebas, validación de Liquibase y build de imagen",
      ["Cada PR corre build, pruebas unitarias e integración, validación de Liquibase y build de imagen",
       "Un PR con una prueba rota no se puede mergear"],
      ["ENC-006", "ENC-007"]),
    t("ENC-009", 0, "infra", ["devops"], 0.25,
      "Bot de revisión con claude-code-action y token de suscripción",
      ["El bot comenta en cada PR del repo",
       "No corre en PRs que vienen de forks",
       "Revisa contra CLAUDE.md, la spec del PR y los ADRs",
       "Tiene un límite de turnos por revisión"],
      ["ENC-008"]),
    t("ENC-010", 0, "infra", ["devops"], 0.5,
      "VM de Oracle: SSH con llave, firewall 22/80/443, Docker, Caddy y DuckDNS",
      ["VM ARM de 1 OCPU y 6 GB con acceso SSH solo por llave",
       "Solo están abiertos los puertos 22, 80 y 443",
       "La app responde por HTTPS con certificado válido",
       "La memoria en reposo queda arriba del 20%"]),
    t("ENC-011", 0, "infra", ["devops"], 0.5,
      "CD a Oracle (GHCR + SSH) y respaldo diario con pg_dump a Object Storage",
      ["Un merge a main llega a Oracle sin pasos manuales",
       "Existe un respaldo diario automático en Object Storage",
       "El primer respaldo ya está en Object Storage"],
      ["ENC-007", "ENC-008", "ENC-010"]),
    t("ENC-012", 0, "infra", ["devops"], 0.25,
      "CLAUDE.md, docs/ con SOW y decisiones, AI Blueprint con el build plan de los 54 ítems",
      ["CLAUDE.md advierte que es Grails 7 e incluye reglas, comandos y Definition of Done",
       "CLAUDE.md obliga a leer el issue con gh issue view antes de escribir una spec",
       "docs/ contiene el SOW y decisiones.md",
       "blueprint/build-plan.md lista ENC-001 a ENC-054 con su número de issue",
       "blueprint/config.json usa git.landing: pull-request",
       "/feature \"ENC-0XX\" genera la spec desde el issue y /complete abre el PR con Closes #N"],
      ["ENC-003", "ENC-009"]),

    # ---------------- Sprint 1 ----------------
    t("ENC-013", 1, "seguridad", ["front"], 1,
      "Layout base responsivo y navegación según el rol",
      ["Usable en 375 px de ancho y en escritorio",
       "Cada rol ve solo las opciones de menú que le corresponden"],
      ["ENC-012"]),
    t("ENC-014", 1, "seguridad", ["back"], 1,
      "Login y logout con Spring Security; roles Administrador, Management y Profesional",
      ["Las rutas están protegidas por rol",
       "La sesión expira tras inactividad",
       "Las contraseñas se guardan con hash"],
      ["ENC-013"]),
    t("ENC-015", 1, "organizacion", ["back", "front"], 1,
      "Catálogo de departamentos",
      ["Alta, cambio y baja lógica de departamentos",
       "Los departamentos no tienen jerarquía"],
      ["ENC-014"]),
    t("ENC-016", 1, "organizacion", ["back", "front"], 2,
      "Catálogo de usuarios internos con rol y departamento",
      ["Cada usuario pertenece a un solo departamento",
       "Dar de baja a un usuario le quita el acceso",
       "Solo el Administrador gestiona usuarios"],
      ["ENC-015"]),
    t("ENC-017", 1, "proveedores", ["back", "front"], 1.5,
      "Catálogo de proveedores",
      ["Alta, cambio y baja lógica de proveedores",
       "Búsqueda por nombre"],
      ["ENC-014"]),
    t("ENC-018", 1, "proveedores", ["back", "front"], 1.5,
      "Contactos de cada proveedor",
      ["El correo es válido y único dentro del proveedor",
       "Una persona en dos proveedores se registra como dos contactos",
       "Baja lógica de contactos"],
      ["ENC-017"]),
    t("ENC-019", 1, "proveedores", ["back", "front"], 1,
      "Asignación de usuarios internos a proveedores",
      ["Un proveedor puede tener varios usuarios internos y viceversa"],
      ["ENC-016", "ENC-017"]),
    t("ENC-020", 1, "proveedores", ["back", "front"], 1,
      "Importación de proveedores y contactos desde Excel",
      ["Muestra una vista previa con los errores por fila",
       "No se guarda nada si el archivo tiene errores"],
      ["ENC-018"]),

    # ---------------- Sprint 2 ----------------
    t("ENC-021", 2, "preguntas", ["back"], 0.5,
      "Modelo de pregunta y datos de desarrollo con Datafaker",
      ["La pregunta tiene código, texto, tipo (escala o abierta) y bandera de activa",
       "En desarrollo se siembran 40 preguntas de escala y 10 abiertas"],
      ["ENC-012"]),
    t("ENC-022", 2, "preguntas", ["back", "front"], 1.5,
      "Importación de preguntas desde CSV",
      ["El CSV tiene las columnas codigo, texto, tipo y activa",
       "La importación es idempotente por código",
       "Se rechaza el archivo si cambia el texto de un código existente",
       "Retirar una pregunta la desactiva, nunca la borra",
       "Solo el Administrador puede importar, con vista previa"],
      ["ENC-021"]),
    t("ENC-023", 2, "campanas", ["back"], 0.5,
      "Bean Clock y modelo de quincena",
      ["Quincenas del 1 al 15 y del 16 a fin de mes en America/Mexico_City",
       "Ningún código usa new Date() ni la hora del sistema directamente",
       "Probado con un reloj fijo"],
      ["ENC-012"]),
    t("ENC-024", 2, "campanas", ["back"], 1.5,
      "Selección del set de preguntas de la quincena",
      [], ["ENC-021", "ENC-023"]),  # cuerpo completo en COMPLETOS
    t("ENC-025", 2, "campanas", ["back"], 1.5,
      "Lanzamiento de quincena e invitaciones",
      ["Se crea una invitación por cada contacto activo",
       "Se guarda la foto de las asignaciones usuario–proveedor del momento del envío",
       "Dar de baja un contacto cancela sus invitaciones abiertas",
       "Lanzar dos veces la misma quincena no duplica invitaciones"],
      ["ENC-019", "ENC-024"]),
    t("ENC-026", 2, "campanas", ["back"], 1,
      "Puerto ServicioCorreo, adaptadores SMTP y Bandeja, y prueba de contrato",
      ["El dominio solo conoce la interfaz ServicioCorreo",
       "La misma especificación Spock de contrato pasa con SMTP (Mailpit) y con Bandeja",
       "El adaptador se elige con la propiedad correo.proveedor"],
      ["ENC-012"]),
    t("ENC-027", 2, "campanas", ["back"], 1,
      "Adaptador de la API de Brevo",
      ["Pasa la prueba de contrato contra WireMock",
       "Se activa con correo.proveedor: brevo",
       "La API key sale de variables de entorno, nunca del código"],
      ["ENC-026"]),
    t("ENC-028", 2, "campanas", ["back"], 1.5,
      "Cola de envío con estados, límites y reintentos; job de Quartz",
      ["Cada invitación tiene estado: pendiente, enviada, recordada, respondida, vencida",
       "Respeta el límite por día (300 con Brevo gratis) y por minuto",
       "Tras un reinicio nadie recibe dos veces el mismo correo",
       "Al despertar, el job procesa todo lo vencido"],
      ["ENC-025", "ENC-026"]),
    t("ENC-029", 2, "campanas", ["back"], 1,
      "Plantillas de invitación y recordatorio; job del día 7",
      ["El recordatorio sale 7 días después del envío de cada invitación, solo si no respondió",
       "Hay un solo recordatorio por invitación",
       "Los correos incluyen la liga al aviso de privacidad",
       "Las plantillas viven en la app, no en el proveedor de correo"],
      ["ENC-028"]),

    # ---------------- Sprint 3 ----------------
    t("ENC-030", 3, "contestador", ["back"], 0.5,
      "Token de invitación y su vigencia",
      ["El token es aleatorio y no adivinable",
       "Vence al iniciar la siguiente quincena",
       "Un token vencido muestra un aviso claro"],
      ["ENC-025"]),
    t("ENC-031", 3, "contestador", ["front"], 1.5,
      "Página pública de la encuesta",
      ["Se abre sin login desde el link del correo",
       "Es responsiva",
       "Muestra la escala 1–5 y los campos abiertos"],
      ["ENC-030"]),
    t("ENC-032", 3, "contestador", ["back"], 1,
      "Guardado parcial y envío final",
      ["El avance se conserva al volver a abrir el link",
       "Después de enviar ya no se puede editar"],
      ["ENC-031"]),
    t("ENC-033", 3, "contestador", ["back", "front"], 1,
      "Validación de respuestas abiertas",
      ["Mínimo 15 caracteres y 3 palabras después de quitar espacios",
       "Rechaza respuestas de solo signos, caracteres repetidos o relleno obvio (n/a, asdf, xxx, ...)",
       "Acepta respuestas como \"ninguno\" o \"nada\"",
       "La misma regla aplica en cliente y servidor"],
      ["ENC-031"]),
    t("ENC-034", 3, "seguimiento", ["back", "front"], 2,
      "Vista de seguimiento por quincena",
      ["Un proveedor cuenta como \"respondió\" si al menos un contacto respondió",
       "Muestra el detalle por contacto"],
      ["ENC-032"]),
    t("ENC-035", 3, "reportes", ["back", "front"], 1.5,
      "Reporte por usuario interno",
      ["Usa la foto de asignaciones del envío",
       "El Profesional solo ve sus proveedores"],
      ["ENC-034"]),
    t("ENC-036", 3, "reportes", ["back", "front"], 1,
      "Reporte por departamento",
      ["Agrupa por el departamento de los usuarios internos asignados"],
      ["ENC-035"]),
    t("ENC-037", 3, "reportes", ["back", "front"], 1,
      "Reporte por rango de fechas",
      ["Filtra por las quincenas dentro del rango"],
      ["ENC-035"]),
    t("ENC-038", 3, "reportes", ["back"], 0.5,
      "Exportación a Excel de los tres reportes",
      ["Genera un archivo .xlsx con los mismos filtros de la pantalla"],
      ["ENC-035", "ENC-036", "ENC-037"]),

    # ---------------- Sprint 4 ----------------
    t("ENC-039", 4, "dashboard", ["back", "front"], 1,
      "Indicador de tasa de respuesta por quincena",
      ["Tasa por proveedor y por contacto",
       "Gráfica por quincena"],
      ["ENC-034"]),
    t("ENC-040", 4, "dashboard", ["back", "front"], 1.5,
      "Satisfacción promedio y su tendencia",
      ["Promedio de la escala 1–5 por quincena",
       "La tendencia es visible"],
      ["ENC-032"]),
    t("ENC-041", 4, "dashboard", ["back", "front"], 1.5,
      "Peores proveedores y peores preguntas",
      ["Top 5 de proveedores con menor satisfacción en la quincena actual",
       "Top 5 de preguntas con menor puntaje en la quincena actual"],
      ["ENC-040"]),
    t("ENC-042", 4, "demo", ["back"], 1.5,
      "Perfil demo con datos sembrados",
      ["Al menos 6 quincenas de historia con respuestas",
       "Solo se activa con el perfil demo"],
      ["ENC-029", "ENC-032"]),
    t("ENC-043", 4, "demo", ["back", "front"], 1,
      "Acceso de un clic por rol y botón \"Lanzar quincena ahora\"",
      ["En el perfil demo se entra con un clic por rol",
       "El botón \"Lanzar quincena ahora\" existe también en producción, solo para Administrador"],
      ["ENC-042"]),
    t("ENC-044", 4, "demo", ["front"], 1,
      "Bandeja visible de la demo",
      ["Muestra los correos del adaptador Bandeja con su link a la encuesta"],
      ["ENC-026", "ENC-042"]),
    t("ENC-045", 4, "demo", ["back", "front"], 1,
      "\"Envíame la invitación a mi correo\"",
      ["Envío real por Brevo",
       "Uno por sesión y por IP",
       "Contenido fijo, sin texto libre"],
      ["ENC-027", "ENC-043"]),
    t("ENC-046", 4, "demo", ["back"], 0.5,
      "Reinicio nocturno de los datos de demo",
      ["Vuelve al estado sembrado sin reiniciar la app"],
      ["ENC-042"]),
    t("ENC-047", 4, "seguridad", ["back"], 1,
      "Revisión transversal de permisos",
      ["Pruebas que confirman qué ve cada rol en reportes y dashboard"],
      ["ENC-038", "ENC-041"]),

    # ---------------- Sprint 5 ----------------
    t("ENC-048", 5, "infra", ["devops"], 1,
      "Cifrado en reposo y en tránsito; cabeceras de seguridad",
      ["El volumen de datos está cifrado",
       "Solo se sirve por HTTPS",
       "HSTS y CSP están configurados"],
      ["ENC-011"]),
    t("ENC-049", 5, "seguridad", ["back"], 1,
      "Revisión de seguridad",
      ["Límite de intentos de login",
       "Los tokens no aparecen en los logs",
       "Las dependencias no tienen vulnerabilidades altas"],
      ["ENC-047"]),
    t("ENC-050", 5, "infra", ["devops"], 2,
      "Prueba de carga del pico posterior al envío",
      ["Escenario de 1,500 contactos abriendo la encuesta",
       "Heap de la JVM y pool de conexiones ajustados con los resultados"],
      ["ENC-042"]),
    t("ENC-051", 5, "infra", ["devops"], 0.5,
      "Restauración de respaldo probada",
      ["Un respaldo de Object Storage se restaura en una base limpia y la app arranca con él"],
      ["ENC-011"]),
    t("ENC-052", 5, "infra", ["devops"], 0.5,
      "Monitoreo de disponibilidad",
      ["Un servicio externo vigila /actuator/health y avisa por correo"],
      ["ENC-011"]),
    t("ENC-053", 5, "docs", ["docs"], 1,
      "README final",
      ["Abre con el video, las capturas y el link a la demo",
       "Explica cómo levantar el proyecto",
       "Enlaza las decisiones y los ADRs"],
      ["ENC-054"]),
    t("ENC-054", 5, "docs", ["docs"], 0.5,
      "Video de la demo de 2 minutos",
      ["Recorre el flujo completo de la demo"],
      ["ENC-046"]),
]

# Tickets que ya tienen su cuerpo completo (no llevan la etiqueta "refinar").
COMPLETOS = {
    "ENC-024": """## Módulo / Sprint / Tipo
campanas · Sprint 2 · back

## Contexto
Cada quincena todos los contactos reciben las mismas 15 preguntas, para que
los resultados entre proveedores sean comparables (ADR-0005).

## Qué se hará
Un servicio que, dado un periodo, devuelve su set de 15 preguntas y lo guarda.
Si el periodo ya tiene set, devuelve el guardado.

## Criterios de aceptación
- [ ] Dado un banco con 40 de escala y 10 abiertas activas, cuando se genera el set, entonces tiene exactamente 12 de escala y 3 abiertas.
- [ ] Dado un periodo con set guardado, cuando se pide otra vez, entonces se devuelve el mismo set sin volver a sortear.
- [ ] Dadas las quincenas consecutivas, ninguna pregunta de escala se repite hasta usar las 40, ni una abierta hasta usar las 10.
- [ ] Al agotarse un tipo, empieza un ciclo nuevo de ese tipo.
- [ ] Una pregunta desactivada nunca se elige.
- [ ] Si no hay suficientes preguntas activas de un tipo, falla con un error claro y no se crea el set.

## Fuera de alcance
- Lanzar la quincena y crear invitaciones (ENC-025).
- Cualquier pantalla.

## Notas técnicas
- Paquete del módulo campanas; lee preguntas solo vía el servicio de preguntas.
- El azar usa un Random inyectable para que las pruebas sean deterministas.
- La fecha sale del bean Clock (ENC-023), nunca de new Date().
- Tabla nueva vía changelog de Liquibase.

## Depende de
ENC-021, ENC-023

## Estimación
1.5 días
""",
}


# ---------------------------------------------------------------------------
# Lógica
# ---------------------------------------------------------------------------
def fmt_dias(d):
    return f"{d:g} día" if d == 1 else f"{d:g} días"


def cuerpo(tk):
    if tk["id"] in COMPLETOS:
        return COMPLETOS[tk["id"]]
    criterios = "\n".join(f"- [ ] {c}" for c in tk["criterios"])
    deps = ", ".join(tk["deps"]) if tk["deps"] else "Ninguna"
    if tk["modulo"] in MODULOS_APP:
        nota_paquete = f"- Código en el paquete del módulo `{tk['modulo']}`.\n"
    else:
        nota_paquete = ""
    return f"""## Módulo / Sprint / Tipo
{tk['modulo']} · Sprint {tk['sprint']} · {' + '.join(tk['tipos'])}

## Contexto
_Por refinar antes de iniciar el sprint._

## Qué se hará
{tk['titulo']}.

## Criterios de aceptación
{criterios}

## Fuera de alcance
_Por refinar antes de iniciar el sprint._

## Notas técnicas
{nota_paquete}- Reglas del proyecto: `CLAUDE.md`, `docs/decisiones.md` y `docs/adr/`.

## Depende de
{deps}

## Estimación
{fmt_dias(tk['dias'])}
"""


def etiquetas(tk):
    labels = list(tk["tipos"]) + [f"mod:{tk['modulo']}"]
    if tk["id"] not in COMPLETOS:
        labels.append("refinar")
    return labels


def calendario(inicio, festivos):
    """Devuelve {sprint: (fecha_inicio, fecha_cierre)} contando días hábiles."""
    feriados = {dt.date.fromisoformat(f) for f in festivos}

    def habil(d):
        return d.weekday() < 5 and d not in feriados

    dia = inicio
    while not habil(dia):
        dia += dt.timedelta(days=1)

    fechas = {}
    for num, _titulo, dias, _hito in SPRINTS:
        arranque, restantes, ultimo = dia, dias, dia
        while restantes > 0:
            if habil(dia):
                ultimo = dia
                restantes -= 1
            dia += dt.timedelta(days=1)
        fechas[num] = (arranque, ultimo)
        while not habil(dia):
            dia += dt.timedelta(days=1)
    return fechas


def gh(*args, stdin=None):
    # encoding="utf-8" es obligatorio: en Windows, sin él, Python manda el cuerpo
    # del issue en cp1252 y GitHub muestra los acentos como "�".
    res = subprocess.run(["gh", *args], input=stdin, capture_output=True,
                         text=True, encoding="utf-8")
    if res.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])} ... falló:\n{res.stderr.strip()}")
    return res.stdout.strip()


def validar_datos():
    ids = [tk["id"] for tk in TICKETS]
    assert len(ids) == len(set(ids)), "IDs de ticket duplicados"
    conocidos = set(ids)
    for tk in TICKETS:
        for d in tk["deps"]:
            assert d in conocidos, f"{tk['id']} depende de {d}, que no existe"
        assert tk["id"] in COMPLETOS or tk["criterios"], f"{tk['id']} no tiene criterios"
    for num, titulo, dias, _ in SPRINTS:
        total = sum(tk["dias"] for tk in TICKETS if tk["sprint"] == num)
        holgura = dias - total
        if holgura < 0:
            sys.exit(f"{titulo}: los tickets suman {total} días y el sprint tiene {dias}")


def main():
    p = argparse.ArgumentParser(description="Carga el backlog en GitHub con gh.")
    p.add_argument("--repo", required=True, help="dueño/repositorio, por ejemplo usuario/encuestas")
    p.add_argument("--inicio", required=True, help="Primer día del Sprint 0 (YYYY-MM-DD)")
    p.add_argument("--festivos", nargs="*", default=FESTIVOS_DEFAULT,
                   help="Días no laborables (YYYY-MM-DD). Por defecto, feriados oficiales de México")
    p.add_argument("--proyecto", type=int, help="Número del GitHub Project para agregar los issues")
    p.add_argument("--owner", help="Dueño del Project (usuario u organización); requerido con --proyecto")
    p.add_argument("--dry-run", action="store_true", help="Muestra el plan sin tocar GitHub")
    p.add_argument("--reparar", action="store_true",
                   help="Reescribe título y cuerpo de los issues ENC que ya existen "
                        "(borra cualquier edición manual que les hayas hecho)")
    a = p.parse_args()

    if a.proyecto and not a.owner:
        sys.exit("--proyecto requiere --owner")

    validar_datos()
    fechas = calendario(dt.date.fromisoformat(a.inicio), a.festivos)

    print("Calendario de sprints (días hábiles, sin fines de semana ni feriados):")
    for num, titulo, dias, _ in SPRINTS:
        ini, fin = fechas[num]
        n = sum(1 for tk in TICKETS if tk["sprint"] == num)
        print(f"  {titulo}: {ini} → {fin} · {dias} días · {n} tickets")

    if a.dry_run:
        print("\n--dry-run: ejemplo del primer issue que se crearía:\n")
        tk = TICKETS[0]
        print(f"Título: {tk['id']} · {tk['titulo']}")
        print(f"Etiquetas: {', '.join(etiquetas(tk))}")
        print(f"Milestone: {SPRINTS[tk['sprint']][1]}\n")
        print(cuerpo(tk))
        print(f"Total: {len(LABELS)} etiquetas, {len(SPRINTS)} milestones, {len(TICKETS)} issues.")
        return

    gh("auth", "status")

    print("\n1/3 Etiquetas")
    for nombre, (color, desc) in LABELS.items():
        gh("label", "create", nombre, "--repo", a.repo, "--color", color,
           "--description", desc, "--force")
        print(f"  ✓ {nombre}")

    print("\n2/3 Milestones")
    existentes = json.loads(gh("api", f"repos/{a.repo}/milestones?state=all&per_page=100"))
    titulos_ms = {m["title"] for m in existentes}
    for num, titulo, dias, hito in SPRINTS:
        if titulo in titulos_ms:
            print(f"  = {titulo} (ya existía)")
            continue
        ini, fin = fechas[num]
        desc = f"{ini} → {fin} · {dias} días hábiles.\nHito: {hito}"
        gh("api", f"repos/{a.repo}/milestones", "-f", f"title={titulo}",
           "-f", f"description={desc}", "-f", f"due_on={fin}T12:00:00Z")
        print(f"  ✓ {titulo} (cierra {fin})")

    print("\n3/3 Issues")
    lista = json.loads(gh("issue", "list", "--repo", a.repo, "--state", "all",
                          "--limit", "1000", "--json", "number,title"))
    ya = {i["title"].split(" ")[0]: i["number"] for i in lista if i["title"].startswith("ENC-")}
    creados = 0
    for tk in TICKETS:
        if tk["id"] in ya:
            if a.reparar:
                num = ya[tk["id"]]
                gh("issue", "edit", str(num), "--repo", a.repo,
                   "--title", f"{tk['id']} · {tk['titulo']}",
                   "--body-file", "-", stdin=cuerpo(tk))
                print(f"  ↻ {tk['id']} (#{num}) reescrito")
            else:
                print(f"  = {tk['id']} (ya existía)")
            continue
        args = ["issue", "create", "--repo", a.repo,
                "--title", f"{tk['id']} · {tk['titulo']}",
                "--body-file", "-",
                "--milestone", SPRINTS[tk["sprint"]][1]]
        for lb in etiquetas(tk):
            args += ["--label", lb]
        url = gh(*args, stdin=cuerpo(tk))
        if a.proyecto:
            gh("project", "item-add", str(a.proyecto), "--owner", a.owner, "--url", url)
        creados += 1
        print(f"  ✓ {tk['id']} → {url}")

    print(f"\nListo: {creados} issues nuevos.")


if __name__ == "__main__":
    # Evita errores al imprimir acentos y símbolos en consolas de Windows.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    try:
        main()
    except RuntimeError as e:
        sys.exit(str(e))
