import calendar
import random
from datetime import datetime, time, timedelta
import json

from models.planting_plan import PlantingPlan, FieldOperation

# get random date between start and end period
def get_random_date(start_month, end_month, year):

    # Convert month to a date in the year 2023 (or any arbitrary year)
    start_date = datetime(year, start_month, 1)
    end_date = datetime(year, end_month+1, 1)

    # Calculate the number of days between the two dates
    delta_days = (end_date - start_date).days

    # Generate a random number of days to add to the start date
    random_days = random.randint(0, delta_days)

    # Return the random date
    return start_date + timedelta(days=random_days) + timedelta(hours=random.randint(0, 23), minutes=random.randint(0, 59), seconds=random.randint(0, 59))


def resolve_planting_year(
    start_date: datetime,
    planting_period_months: tuple[int, int],
    lead_time_days: int,
) -> int:
    """Determine the year in which the planting date should be scheduled.

    Rule (Befund B2, Issue #58): The earliest admissible planting date is
    ``start_date + lead_time_days`` (so that soil-preparation operations have
    enough lead time). If this earliest date still lies before the end of the
    planting window in the start year, the planting is scheduled in the
    **start year**; otherwise in the **following year**.

    Args:
        start_date: Simulation start date.
        planting_period_months: ``(start_month, end_month)`` of the planting
            window (e.g. ``(4, 5)`` for April–May).
        lead_time_days: Maximum lead time required by the soil-preparation
            operations (absolute value of the largest
            ``min_days_to_target`` in the ``soil_preparation`` phase).

    Returns:
        The year (``int``) in which the planting date should be scheduled.
    """
    earliest = start_date + timedelta(days=lead_time_days)
    end_month = planting_period_months[1]
    last_day_of_end_month = calendar.monthrange(start_date.year, end_month)[1]
    window_end_start_year = datetime(start_date.year, end_month, last_day_of_end_month)
    if earliest <= window_end_start_year:
        return start_date.year
    return start_date.year + 1


def get_random_planting_date(
    start_date: datetime,
    planting_period_months: tuple[int, int],
    lead_time_days: int,
) -> datetime:
    """Random planting date within the reachable planting window.

    Determines the planting year via :func:`resolve_planting_year` and then
    draws a random date inside the intersection of the planting window and
    ``[start_date + lead_time_days, ∞)``. The date is never earlier than
    ``start_date + lead_time_days`` (Befund B2, Issue #58).

    Args:
        start_date: Simulation start date.
        planting_period_months: ``(start_month, end_month)`` of the planting
            window.
        lead_time_days: Maximum lead time of soil-preparation operations.

    Returns:
        A random :class:`datetime.datetime` within the constrained planting
        window.
    """
    year = resolve_planting_year(start_date, planting_period_months, lead_time_days)
    start_month, end_month = planting_period_months

    window_start = datetime(year, start_month, 1)
    earliest = start_date + timedelta(days=lead_time_days)
    if earliest > window_start:
        window_start = earliest

    last_day = calendar.monthrange(year, end_month)[1]
    window_end = datetime(year, end_month, last_day)

    delta_days = (window_end - window_start).days
    if delta_days < 0:
        # Defensive fallback: should not happen if resolve_planting_year is
        # correct, but guards against degenerate inputs.
        delta_days = 0
    random_days = random.randint(0, delta_days)
    return window_start + timedelta(days=random_days) + timedelta(
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )

def get_random_date_in_range(min_days_offset, max_days_offset, target_date) -> datetime:
    
    """
    Get a random date within a specified range of days from a target date.
    
    :param min_days_offset: Minimum number of days to offset from the target date.
    :param max_days_offset: Maximum number of days to offset from the target date.
    :param target_date: The target date to offset from.
    :return: A random datetime object within the specified range.
    """
    days_offset = random.randint(min_days_offset, max_days_offset)
    return target_date + timedelta(days=days_offset)


def get_operations_by_phase(planting_plan: PlantingPlan, phase_name: str) -> list[FieldOperation]:
    """
    Get the operations for a specific phase in the planting plan.
    
    :param planting_plan: The PlantingPlan object containing the phases and operations.
    :param phase_name: The name of the phase to retrieve operations for.
    :return: A list of FieldOperations for the specified phase.
    """
    for phase in planting_plan.phases:
        if phase.phase_name == phase_name:
            return phase.operations
    return []

def get_protection_categories():
    # read the file in config/categories.json
    
    with open('config/category.json', 'r') as file:
        data = json.load(file)
        # If data is a list of categories, just return it
        return data
    
def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing invalid characters and truncating to 50 characters.
    
    :param filename: The original filename to sanitize.
    :return: A sanitized version of the filename.
    """
    # Remove invalid characters and truncate to 50 characters
    MAX_FILENAME_LENGTH = 50
    ALLOWED_FILENAME_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-. "
    
    sanitized = ''.join(c for c in filename if c.isalnum() or c in ALLOWED_FILENAME_CHARS).rstrip()
    sanitized = sanitized.replace(' ', '_')
    return sanitized[:MAX_FILENAME_LENGTH]

def assign_sequential_time(
    date: datetime,
    min_start: time = time(6, 0),
    max_end: time = time(17, 0),
) -> datetime:
    """Ziehe einen zufälligen Zeitpunkt am ``date`` im Fenster ``[min_start, max_end]``.

    Wird von ``PlantingPlanService`` / ``ProtectionPlanService`` genutzt, um pro
    Tag **strikt monoton steigende** Zeitpunkte zu vergeben (Befund B7,
    Issue #66 / P2-2). Der Aufrufer verwaltet den Cursor ``min_start`` aus dem
    zuletzt vergebenen Zeitpunkt desselben Tages.

    P3-5 (Issue #83): ``PlantingPlanService`` übergibt explizit ein erweitertes
    Fenster ``[05:00, 20:00]`` (KAR-045 ``start_hour_range: [5, 20]``), um
    längere Arbeitszeiten zu ermöglichen. Die Defaults bleiben auf
    ``[06:00, 17:00]``, um den Zufallszustand für ``ProtectionPlanService``
    nicht zu verschieben (Befund B7 / KAR-021).

    Garantie: Der Rückgabewert liegt **strikt nach** ``min_start`` (mindestens
    1 Sekunde später), sofern das Restfenster >= 1 Minute ist. Dadurch bleibt
    die Intra-Tages-Sequenz bei aufeinanderfolgenden Einzel-Calls erhalten
    (``CalendarDrivenRunner.tick()`` ruft ``get_events_for_ops`` pro Operation
    einzeln auf).

    Faellt das Restfenster auf < 1 Minute zusammen (z. B. > 11 Operationen am
    selben Tag, praktisch nicht erreichbar bei Kartoffel-Saison mit max. ~5
    Ops/Tag), wird ``min_start + 1 Minute`` zurueckgegeben - deterministischer
    Randfall statt Exception. In diesem Fall kann der Rueckgabewert ``max_end``
    ueberschreiten (dokumentierter Edge-Case, KAR-045 nicht verschlechtert da
    nur bei Cursor-Erschoepfung).

    Args:
        date: Das Kalenderdatum (``datetime`` oder ``date``), auf dem der
            Zeitpunkt liegt.
        min_start: Fruehester zulaessiger Zeitpunkt (inklusive). Default 06:00.
        max_end: Spaetester zulaessiger Zeitpunkt (inklusive). Default 17:00.

    Returns:
        Ein ``datetime`` am ``date`` mit Uhrzeit strikt nach ``min_start`` und
        <= ``max_end`` (ausser im dokumentierten Randfall).
    """
    earliest = datetime.combine(date, min_start)
    latest = datetime.combine(date, max_end)
    window_seconds = int((latest - earliest).total_seconds())

    if window_seconds < 60:
        # Deterministischer Randfall: Fenster erschöpft, kein Platz für
        # Zufallsstreuung. min_start + 1 Minute bleibt monoton.
        return earliest + timedelta(minutes=1)

    # Strikt nach min_start: offset ∈ [1, window_seconds] garantiert
    # Monotonie bei aufeinanderfolgenden Calls für dasselbe Datum.
    offset = random.randint(1, window_seconds)
    return earliest + timedelta(seconds=offset)
