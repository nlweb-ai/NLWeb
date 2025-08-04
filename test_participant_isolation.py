#!/usr/bin/env python3
"""Isolated test to debug participant storage issue."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code/python'))

from datetime import datetime
from chat.schemas import Conversation, ParticipantInfo, ParticipantType

# Create conversation with participants
conv = Conversation(
    conversation_id="test_conv",
    created_at=datetime.utcnow(),
    active_participants=set(),
    queue_size_limit=1000,
    message_count=0,
    metadata={"title": "Test"}
)

# Add participants
p1 = ParticipantInfo(
    participant_id="user_1",
    name="User One",
    participant_type=ParticipantType.HUMAN,
    joined_at=datetime.utcnow()
)

p2 = ParticipantInfo(
    participant_id="user_2", 
    name="User Two",
    participant_type=ParticipantType.HUMAN,
    joined_at=datetime.utcnow()
)

print(f"Created p1: type={type(p1)}, value={p1}")
print(f"Created p2: type={type(p2)}, value={p2}")

conv.add_participant(p1)
conv.add_participant(p2)

print(f"\nAfter adding participants:")
print(f"  active_participants type: {type(conv.active_participants)}")
print(f"  Number of participants: {len(conv.active_participants)}")

for i, p in enumerate(conv.active_participants):
    print(f"  Participant {i}: type={type(p)}, value={p}")
    
# Test to_dict
conv_dict = conv.to_dict()
print(f"\nConverted to dict:")
print(f"  active_participants in dict: {conv_dict['active_participants']}")

# Try to access participant_id from each participant
print("\nAccessing participant_id from participants:")
for p in conv.active_participants:
    try:
        print(f"  {p.participant_id}: {p.name}")
    except AttributeError as e:
        print(f"  ERROR: {e} - participant is {type(p)}: {p}")