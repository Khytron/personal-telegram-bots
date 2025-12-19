from telethon import TelegramClient, events
import random
import asyncio

# 1. Insert your details from my.telegram.org
api_id = 33411117       # Replace with your API ID (integer)
api_hash = '6dfbd3acbf7ef420fe2bac53b3406432' # Replace with your API Hash (string)

# 2. Define the Target Group
# You can use the group's username (e.g., 'groupusername') or ID.
# To find an ID, you can forward a message from the group to a bot like @userinfobot.
TARGET_GROUP = -1001869302435 #-5065987554

# --- STATE TRACKING ---
# We store the IDs of people we are currently "dealing with"
# Dictionary to store {sender_id: original_group_message_object}
active_customers = {}

# --- TRACKING FILTER ---
tracking_filter = None

# --- UNWANTED REQUESTS FILTER ---
unwanted_orders = []

# --- GLOBAL CONTROL SWITCH ---
# True = Bot works normally. False = Bot ignores everything.
bot_active = True

# 3. The Message you want to send
PRIVATE_RESPONSE = "Rm4?"

# 4. Force create a new event loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
# ---------------------------

# Create the client (this will ask you to login via terminal the first time)
client = TelegramClient('my_safe_userbot', api_id, api_hash, loop=loop)

# ---------------------------------------------------------
# PART 1: THE REMOTE CONTROL (Commands to Yourself)
# ---------------------------------------------------------
# This listens for messages YOU send (outgoing=True) anywhere.
# Best practice: Send these to your "Saved Messages".
@client.on(events.NewMessage(outgoing=True, pattern=r'^\.(pause|resume|status|track|untrack)( .+)?$'))
async def control_handler(event):
    global bot_active
    global tracking_filter

    # Split command from arguments (e.g., ".track burger" -> "burger")
    raw_text = event.raw_text.strip()
    cmd_parts = raw_text.split(" ", 1)
    command = cmd_parts[0].lower()
    args = cmd_parts[1] if len(cmd_parts) > 1 else None

    if command == '.pause':
        bot_active = False
        active_customers = {}  # Clear active customers when pausing
        # Edit your command message to confirm receipt
        await event.edit("⏸️ **PAUSED**: Auto-reply is now OFF.")
        print("--- [CONTROL] Bot Paused by User ---")

    elif command == '.resume':
        bot_active = True
        await event.edit("▶️ **RESUMED**: Auto-reply is now ON.")
        print("--- [CONTROL] Bot Resumed by User ---")

    elif command == '.status':
        status_text = "✅ RUNNING" if bot_active else "⏸️ PAUSED"
        await event.edit(f"**Bot Status:** {status_text}")
        print(f"--- [CONTROL] Bot Status Checked: {status_text} ---")

    elif command == '.untrack':
        tracking_filter = None
        await event.edit("🗑️ Cleared tracking filter." )
        print("--- [CONTROL] Tracking Filter Cleared ---")

    elif command == '.track':
        if args:
            tracking_filter = args.lower()
            await event.edit(f"🎯 **TRACKING ENABLED**: Only accepting orders containing: **'{tracking_filter}'**")
            print(f"--- [CONTROL] Tracking Filter Set to '{tracking_filter}' ---")
        else:
            await event.edit("⚠️ Please provide a keyword to track.    Usage: `.track <keyword>`")
            print("--- [CONTROL] Track Command Used Without Keyword ---")



# ---------------------------------------------------------
# PART 2: THE TRIGGER (Group -> PM)
# ---------------------------------------------------------
@client.on(events.NewMessage(chats=TARGET_GROUP))
async def handler(event):
    global bot_active
    
    # IMMEDIATE STOP if paused
    if not bot_active:
        return
    
    # 1. BUSY CHECK
    # If we are already tracking someone, IGNORE new requests.
    if len(active_customers) > 0:
        print(f"⚠️ Busy with a customer. Ignoring request from {event.sender_id}")
        return
    
    #  Check if message is from another user (not you)
    # if event.out:
    #     return

    # 2. Get the text and check the specific trigger phrase
    # .strip() removes accidental spaces at the start/end
    # .upper() makes it case-insensitive (works for "Order Template" or "ORDER TEMPLATE")
    text = event.raw_text.strip()

    
    if text.upper().startswith("ORDER TEMPLATE"):
        # If tracking specific requests
        if tracking_filter:
            if tracking_filter not in text.lower():
                 print(f"Filtered out a request not containing '{tracking_filter}'. No PM sent.")
                 return
        
        # Filter unwanted requests
        

        try:
            sender = await event.get_sender()
            sender_id = sender.id
            
            print(f"Trigger received from {sender_id}. Sending PM...")

            
            # Add them to our "Watch List"
            # STORE THE MESSAGE OBJECT (so we can forward it later)
            active_customers[sender_id] = event.message
            

            # --- SAFETY MECHANISM: HUMAN DELAY ---
            # Wait between 5 and 12 seconds before sending
            wait_time = random.randint(5, 12)
            print(f"   -> Waiting {wait_time} seconds to simulate human typing...")
            await asyncio.sleep(wait_time)

            # 3. Send the PRIVATE message

            # If there is KK9 or KK13 in the message, raise the price
            if "kk9" in text.lower() or "kk13" in text.lower():
                await client.send_message(sender_id, "Rm5?")
            else:
                # We use client.send_message instead of event.reply
                await client.send_message(sender_id, PRIVATE_RESPONSE)

            
            
            print(f"Sent private message to {sender_id}")

        except Exception as e:
            print(f"Error sending DM to {sender_id}: {e}")

# ---------------------------------------------------------
# PART 3: THE FOLLOW-UP (Private Message -> "Ok")
# ---------------------------------------------------------
@client.on(events.NewMessage(incoming=True))
async def followup_handler(event):
    global bot_active
    
    # 1. Check if bot is on and message is Private
    if not bot_active: return
    if not event.is_private: return

    # 2. IMPORTANT: Only reply if this person is in our "Active List"
    # This prevents you from replying "Ok" to your friends/family
    sender_id = event.sender_id
    if sender_id not in active_customers:
        return

    # 3. Wait 5-8 seconds before replying to simulate human behavior
    wait_time = random.randint(5, 8)
    print(f"   -> Customer {sender_id} replied. Waiting {wait_time}s to say 'Ok'...")
    await asyncio.sleep(wait_time)

    # 4. Reply "Ok"
    try:
        await event.reply("Ok")
        print(f"   -> Replied 'Ok' to {sender_id}")

        # 5. FORWARDING LOGIC
        print(f"   -> Forwarding conversation to Saved Messages...")

        # A. Forward the Original Group Message (retrieved from memory)
        original_msg = active_customers[sender_id]
        await client.forward_messages('me', original_msg)

        # B. Forward the Customer's Reply (the current event)
        await client.forward_messages('me', event.message)
        
        # 6. Remove them from list so we don't say "Ok" forever
        del active_customers[sender_id]
        
    except Exception as e:
        print(f"   -> Error replying Ok: {e}")

print("Listening for 'ORDER TEMPLATE' requests...")
client.start()
client.run_until_disconnected()