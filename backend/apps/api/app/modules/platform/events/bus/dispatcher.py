from app.modules.platform.events.queues.queue_manager import queue_manager
from app.services.event_consumers import consume_event


def dispatch_queue_message(queue: str, envelope: dict) -> dict:
    result = queue_manager.process_next(queue)
    if result.status == "processed" and result.envelope:
        consume_event(queue=queue, envelope=result.envelope)
    return {"status": result.status, "queue": queue}
