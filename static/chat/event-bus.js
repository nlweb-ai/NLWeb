class EventBus {
    constructor() {
        this.events = new Map();
        this.debug = false;
    }

    on(event, callback) {
        if (!this.events.has(event)) {
            this.events.set(event, new Set());
        }
        this.events.get(event).add(callback);
        
        if (this.debug) {
            console.log(`EventBus: Subscribed to '${event}'`);
        }

        // Return unsubscribe function
        return () => this.off(event, callback);
    }

    off(event, callback) {
        if (this.events.has(event)) {
            this.events.get(event).delete(callback);
            if (this.events.get(event).size === 0) {
                this.events.delete(event);
            }
            
            if (this.debug) {
                console.log(`EventBus: Unsubscribed from '${event}'`);
            }
        }
    }

    emit(event, data) {
        if (this.debug) {
            console.log(`EventBus: Emitting '${event}'`, data);
        }

        if (this.events.has(event)) {
            const callbacks = this.events.get(event);
            callbacks.forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`EventBus: Error in '${event}' listener:`, error);
                }
            });
        }
    }

    setDebug(enabled) {
        this.debug = enabled;
    }
}

// Export singleton instance
export default new EventBus();