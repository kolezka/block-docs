from jobs.queue import enqueue


def send_welcome_email(user_id, address):
    return enqueue("send_email", {"user_id": user_id, "address": address, "template": "welcome"})
