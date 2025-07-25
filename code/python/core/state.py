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
        self._tool_router_event = asyncio.Event()
       
    def start_precheck_step(self, step_name):
        """Synchronous version for immediate state update"""
        self.precheck_step_state[step_name] = self.__class__.INITIAL

    async def precheck_step_done(self, step_name):
        async with self._state_lock:
            self.precheck_step_state[step_name] = self.__class__.DONE
            if step_name == "Decon":
                self._decon_event.set()
            elif step_name == "ToolSelector":
                self._tool_router_event.set()
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
    
    async def wait_for_tool_routing(self):
        """Wait for tool routing to complete"""
        await self._tool_router_event.wait()
        return self.is_tool_routing_done()
    
    def is_tool_routing_done(self):
        if "ToolSelector" in self.precheck_step_state:
            return self.precheck_step_state["ToolSelector"] == self.__class__.DONE
        else:
            return False
    
    def should_abort_fast_track(self):
        """
        Consolidate all fast track abort conditions into a single method.
        Returns True if fast track should be aborted, False otherwise.
        """
        handler = self.handler
        
        # 1. Query already marked as done (from relevance detection or required info)
        if handler.query_done:
            return True
        
        # 2. Query is irrelevant to the site
        if hasattr(handler, 'query_is_irrelevant') and handler.query_is_irrelevant:
            return True
        
        # 3. Required information is missing
        if hasattr(handler, 'required_info_found') and not handler.required_info_found:
            return True
        
        # 4. Decontextualization is required
        if hasattr(handler, 'requires_decontextualization') and handler.requires_decontextualization:
            return True
        
        # 5. Connection is lost
        if not handler.connection_alive_event.is_set():
            return True
        
        # 6. Tool routing indicates the top tool is not 'search'
        if (hasattr(handler, 'tool_routing_results') and 
            handler.tool_routing_results and 
            isinstance(handler.tool_routing_results, list) and
            len(handler.tool_routing_results) > 0):
            
            top_tool_result = handler.tool_routing_results[0]
            if top_tool_result["tool"].name != 'search':
                return True
        
        return False
    
    def abort_fast_track_if_needed(self):
        """
        Check all abort conditions and set the abort event if needed.
        Returns True if fast track was aborted, False otherwise.
        """
        if self.should_abort_fast_track():
            self.handler.abort_fast_track_event.set()
            return True
        return False