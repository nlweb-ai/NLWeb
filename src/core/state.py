# state.py
import asyncio

class NLWebHandlerState:

    INITIAL = 0
    DONE = 2

    def __init__(self, handler):
        self.handler = handler
        self.precheck_step_state = {}
        self._state_lock = asyncio.Lock()
        self._decon_event = asyncio.Event()
       
    def start_precheck_step(self, step_name):
        """Synchronous version for immediate state update"""
        self.precheck_step_state[step_name] = self.__class__.INITIAL

    async def precheck_step_done(self, step_name):
        async with self._state_lock:
            self.precheck_step_state[step_name] = self.__class__.DONE
            if step_name == "Decon":
                self._decon_event.set()
            # Check if all steps are done
            if all(state == self.__class__.DONE for state in self.precheck_step_state.values()):
                self.handler.pre_checks_done_event.set()
    
    def set_pre_checks_done(self):
        """Synchronous version for compatibility"""
        self.handler.pre_checks_done_event.set()

    async def pre_check_approval(self):
        """Wait for all pre-checks to complete"""
        await self.handler.pre_checks_done_event.wait()
        if self.handler.query_done:
            return False
        if not self.handler.connection_alive_event.is_set():
            return False
        return True

    async def wait_for_decontextualization(self):
        """Wait for decontextualization to complete"""
        await self._decon_event.wait()
        return self.is_decontextualization_done()

    def is_decontextualization_done(self):
        if "Decon" in self.precheck_step_state:
            return self.precheck_step_state["Decon"] == self.__class__.DONE
        else:
            return False