def earlier_thread_messages(messages, target):
    return sorted(
        [m for m in messages if m.thread_id == target.thread_id and m.timestamp < target.timestamp],
        key=lambda m: m.timestamp,
    )


def select_grounding_sources(messages, target):
    earlier = earlier_thread_messages(messages, target)
    concrete = [m for m in earlier if '://' in m.body or 'url' in m.body.lower()]
    return concrete[-3:] if concrete else earlier[-3:]


def retrieve_for_grounding(messages, target):
    return select_grounding_sources(messages, target)
