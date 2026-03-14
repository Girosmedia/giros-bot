"""Re-exports SchedulingResult desde services.scheduling.

Las implementaciones concretas (CalendlyScheduler, GoogleCalendarScheduler)
importan desde aquí para que el tipo coincida exactamente con el definido
en el Protocol ISchedulingService — evitando el error de tipo duplicado.
"""

from ...services.scheduling import SchedulingResult

__all__ = ["SchedulingResult"]
