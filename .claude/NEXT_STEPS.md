# Next Steps

## Immediate Tasks

1. **Test Timestamp Consistency**
   - Verify all messages now have consistent millisecond timestamps
   - Test message replay with proper timestamp ordering
   - Ensure client correctly handles new timestamp format

2. **Verify Storage**
   - Confirm all streaming messages include timestamps
   - Check messages.jsonl for timestamp consistency
   - Test join/replay functionality with timestamped messages

## Future Improvements

1. **Message Ordering**
   - Implement proper message sequencing for concurrent messages
   - Handle out-of-order message delivery

2. **Performance**
   - Optimize message storage for large conversations
   - Implement message pagination for long conversations

3. **Error Handling**
   - Add retry logic for failed message delivery
   - Improve WebSocket reconnection handling

4. **Features**
   - Add typing indicators
   - Implement read receipts
   - Add message editing capability