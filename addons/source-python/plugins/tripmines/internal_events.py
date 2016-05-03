from traceback import format_exc

from core import echo_console


class InternalEventManager(dict):
    def register_event_handler(self, event_name, handler):
        if event_name not in self:
            self[event_name] = []

        if handler in self[event_name]:
            raise ValueError("Handler {} is already registered to "
                             "handle '{}'".format(handler, event_name))

        self[event_name].append(handler)

    def unregister_event_handler(self, event_name, handler):
        if event_name not in self:
            raise KeyError("No '{}' event handlers are registered".format(
                event_name))

        self[event_name].remove(handler)

        if not self[event_name]:
            del self[event_name]

    def fire(self, event_name, event_var):
        exceptions = []
        for handler in self.get(event_name, ()):
            try:
                handler(event_var)
            except Exception as e:
                exceptions.append(e)
                echo_console(format_exc())

        if exceptions:
            echo_console("{} exceptions were raised during "
                  "handling of '{}' event".format(len(exceptions), event_name))

internal_event_manager = InternalEventManager()


class InternalEvent:
    def __init__(self, event_name):
        self.event_name = event_name

    def __call__(self, handler):
        self.register(handler)

    def register(self, handler):
        internal_event_manager.register_event_handler(self.event_name, handler)

    def unregister(self, handler):
        internal_event_manager.unregister_event_handler(
            self.event_name, handler)

    @staticmethod
    def fire(event_name, **event_var):
        internal_event_manager.fire(event_name, event_var)
