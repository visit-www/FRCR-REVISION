"""
SM-2 Spaced Repetition Algorithm

Simplified 3-button rating system:
  0 = Again (wrong / complete blackout)
  1 = Good  (correct with effort)
  2 = Easy  (perfect, no hesitation)
"""

from datetime import date, timedelta, datetime


def calculate_next_interval(quality, repetition_number, ease_factor, interval_days):
    """
    Calculate next review interval based on SM-2 algorithm.

    Returns:
        (new_interval_days, new_ease_factor, new_repetition_number)
    """
    if quality == 0:
        # Again: reset
        new_rep = 0
        new_interval = 1
        new_ease = max(1.3, ease_factor - 0.2)

    elif quality == 1:
        # Good: normal progression
        new_rep = repetition_number + 1
        new_ease = ease_factor
        if new_rep == 1:
            new_interval = 1
        elif new_rep == 2:
            new_interval = 6
        else:
            new_interval = round(interval_days * new_ease)

    elif quality == 2:
        # Easy: fast-track
        new_rep = repetition_number + 1
        new_ease = min(2.5, ease_factor + 0.1)
        if new_rep == 1:
            new_interval = 4
        elif new_rep == 2:
            new_interval = 10
        else:
            new_interval = round(interval_days * new_ease * 1.3)

    else:
        raise ValueError(f"Invalid quality: {quality}. Must be 0, 1, or 2.")

    return max(1, new_interval), new_ease, new_rep


def update_progress_on_answer(progress, quality):
    """
    Update a UserQAProgress instance in place based on answer quality.
    Does NOT commit to database — caller must commit.
    """
    new_interval, new_ease, new_rep = calculate_next_interval(
        quality=quality,
        repetition_number=progress.repetition_number,
        ease_factor=progress.ease_factor,
        interval_days=progress.interval_days,
    )

    progress.interval_days = new_interval
    progress.ease_factor = new_ease
    progress.repetition_number = new_rep
    progress.next_review_date = date.today() + timedelta(days=new_interval)
    progress.last_reviewed_at = datetime.utcnow()

    if quality == 0:
        progress.times_incorrect += 1
    else:
        progress.times_correct += 1
