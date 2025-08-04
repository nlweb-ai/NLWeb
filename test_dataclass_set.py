#!/usr/bin/env python3
"""Test if dataclass with Set works correctly."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code/python'))

from dataclasses import dataclass
from typing import Set
from datetime import datetime
from chat.schemas import Conversation, ParticipantInfo, ParticipantType

# Test 1: Direct manipulation
print("=== Test 1: Direct manipulation ===")
conv1 = Conversation(
    conversation_id="test1",
    created_at=datetime.utcnow(),
    active_participants=set(),
    queue_size_limit=1000
)

p1 = ParticipantInfo("user1", "User 1", ParticipantType.HUMAN, datetime.utcnow())
conv1.active_participants.add(p1)

print(f"Conv1 participants after add: {conv1.active_participants}")
print(f"First participant type: {type(list(conv1.active_participants)[0])}")

# Test 2: Assignment
print("\n=== Test 2: Assignment ===")
conv2 = Conversation(
    conversation_id="test2",
    created_at=datetime.utcnow(),
    active_participants=set(),
    queue_size_limit=1000
)

# Try assigning a set of strings (this should be the bug)
conv2.active_participants = {"user1", "user2"}  # Wrong!
print(f"Conv2 participants after string assignment: {conv2.active_participants}")
print(f"Type of set: {type(conv2.active_participants)}")
if conv2.active_participants:
    print(f"First element type: {type(list(conv2.active_participants)[0])}")

# Test 3: Proper assignment
print("\n=== Test 3: Proper assignment ===")
conv3 = Conversation(
    conversation_id="test3",
    created_at=datetime.utcnow(),
    active_participants=set(),
    queue_size_limit=1000
)

p2 = ParticipantInfo("user2", "User 2", ParticipantType.HUMAN, datetime.utcnow())
p3 = ParticipantInfo("user3", "User 3", ParticipantType.HUMAN, datetime.utcnow())
conv3.active_participants = {p2, p3}  # Correct!
print(f"Conv3 participants after proper assignment: {conv3.active_participants}")
print(f"First participant type: {type(list(conv3.active_participants)[0])}")

# Test 4: Check if we can catch the error
print("\n=== Test 4: Error detection ===")
conv4 = Conversation(
    conversation_id="test4",
    created_at=datetime.utcnow(),
    active_participants=set(),
    queue_size_limit=1000
)

# Simulate the bug
conv4.active_participants = {"string1", "string2"}

# Try to access participant_id
try:
    for p in conv4.active_participants:
        print(f"Participant ID: {p.participant_id}")
except AttributeError as e:
    print(f"ERROR: {e}")
    print(f"This is the bug! active_participants contains: {conv4.active_participants}")