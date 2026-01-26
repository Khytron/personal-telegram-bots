from telethon import TelegramClient, events
import random
import asyncio
import csv
import os
from datetime import datetime

# 1. Insert your details from my.telegram.org
api_id = 33411117       # Replace with your API ID (integer)
api_hash = '6dfbd3acbf7ef420fe2bac53b3406432' # Replace with your API Hash (string)

# 2. Define the Target Group
# You can use the group's username (e.g., 'groupusername') or ID.
# To find an ID, you can forward a message from the group to a bot like @userinfobot.
TARGET_GROUP = -1001869302435 # (OnDeWei Group: -1001869302435, Test Group: -5065987554)

# --- STATE TRACKING ---
# We store the IDs of people we are currently "dealing with"
# Dictionary to store {sender_id: original_group_message_object}
customers = {}
active_customers = {}
replied_to = set() # Track who we already said "Ok" to
current_session_cafe = None # Track the cafe of the first accepted customer

# --- SESSION DATA ---
session_total_profit = 0
session_total_delivery = 0

# --- TRACKING FILTER ---
tracking_filter = None

# --- UNWANTED REQUESTS FILTER ---
unwanted_requests = ["air", "ais", "ice", "tea"]

# --- PLACES OUTSIDE UM ---
places_outside_um = ["kk13", "ipgkkbm", "vista", "kerinchi"]

# --- GLOBAL CONTROL SWITCH ---
# True = Bot works normally. False = Bot ignores everything.
bot_active = True

# 3. The Message you want to send
PRIVATE_RESPONSE = "Rm4?"

# 4. Force create a new event loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# 5. Lock for concurrency safety
processing_lock = asyncio.Lock()
# ---------------------------

# Create the client (this will ask you to login via terminal the first time)
client = TelegramClient('my_safe_userbot', api_id, api_hash, loop=loop)

# ---------------------------------------------------------
# PART 1: THE REMOTE CONTROL (Commands to Yourself)
# ---------------------------------------------------------
# This listens for messages YOU send (outgoing=True) anywhere.
# Best practice: Send these to your "Saved Messages".
@client.on(events.NewMessage(outgoing=True, pattern=r'^\.(pause|resume|status|track|untrack|done|active|finish|clear|help|avoid|reset_unwanted|clear_customer|info|setprice)( .+)?$'))
async def control_handler(event):
    global bot_active
    global tracking_filter
    global active_customers
    global customers
    global replied_to
    global session_total_profit
    global session_total_delivery
    global unwanted_requests
    global current_session_cafe
    global PRIVATE_RESPONSE

    # Split command from arguments (e.g., ".track burger" -> "burger")
    raw_text = event.raw_text.strip()
    cmd_parts = raw_text.split(" ", 1)
    command = cmd_parts[0].lower()
    args = cmd_parts[1] if len(cmd_parts) > 1 else None

    if command == '.pause':
        bot_active = False
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

    elif command == '.done':
        # Calculate profit, add to session total profit
        for customer_id, customer_msg in active_customers.items():
            if ("kk13" in customer_msg.lower()):
                session_total_profit += 5 # Add RM5 to total profit
            else:
                session_total_profit += 4 # Add Rm4 to total profit

            session_total_delivery += 1 # Increment total transactions
        
        customers = {} # Clear customers
        active_customers = {}  # Clear active customers
        replied_to.clear() # Clear reply tracking
        current_session_cafe = None
        await event.edit("⏸️ **FINISHED**: Finished the delivery(s).")
        print("--- [CONTROL] Finished delivery(s) ---")

    elif command == '.active':
        if not event.is_reply:
            await event.edit("⚠️ Reply to a message to check active status.")
            return

        # Get the message you replied to
        reply_msg = await event.get_reply_message()
        
        # Get the string of the message
        target_text = reply_msg.raw_text.strip()
        
        # Search for the sender_id in customers based on the text
        found_id = None
        for sender_id, stored_msg in customers.items():
            if stored_msg.raw_text.strip() == target_text:
                found_id = sender_id
                break
        
        if found_id:
            active_customers[found_id] = target_text
            await event.edit(f"✅ Active Customer: `{found_id}`")
            print(f"--- [CONTROL] Active customer: {found_id} ---")
        else:
            await event.edit("❌ No customer found with that text.")
            print("--- [CONTROL] .active: No match found ---")

    elif command == '.finish':
        await event.edit(f"--- SESSION STATS ---\nTotal Profit: RM{session_total_profit} ✅\nTotal Delivery: {session_total_delivery} ")
        print("--- [CONTROL] Finished a session ---")
        print(f"Total Profit: RM{session_total_profit} ✅")
        print(f"Total Delivery: {session_total_delivery} ")
        
        # --- CSV RECORDING LOGIC ---
        csv_file = "OnDeWeiProfit.csv"
        today_str = datetime.now().strftime("%d-%m-%y")
        
        # 1. Ensure file exists with header
        if not os.path.exists(csv_file):
            with open(csv_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Date", "Total_Profit", "Total_Delivery"])
        
        # 2. Read and Update Data
        rows = []
        date_found = False
        
        try:
            with open(csv_file, "r", newline="") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header:
                    rows.append(header)
                else:
                    rows.append(["Date", "Total_Profit", "Total_Delivery"])
                
                for row in reader:
                    if row and row[0] == today_str:
                        # Found today's record: Update it
                        # row[1] is profit, row[2] is transactions
                        current_saved_profit = int(row[1])
                        current_saved_delivery = int(row[2])
                        
                        new_profit = current_saved_profit + session_total_profit
                        new_delivery = current_saved_delivery + session_total_delivery
                        
                        rows.append([today_str, new_profit, new_delivery])
                        date_found = True
                    else:
                        rows.append(row)
            
            # 3. If date not found, add new record
            if not date_found:
                rows.append([today_str, session_total_profit, session_total_delivery])
                
            # 4. Write back to file
            with open(csv_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerows(rows)
                
            print(f"--- [SYSTEM] Saved session stats to {csv_file} ---")
            
        except Exception as e:
            print(f"--- [ERROR] Could not save to CSV: {e} ---")

        current_session_cafe = None
        bot_active = False

    elif command == '.clear':
        customers = {} # Clear customers
        active_customers = {}  # Clear active customers
        replied_to.clear() # Clear reply tracking
        current_session_cafe = None
        
        await event.edit("⏸️ **CLEARED**: Active customers cleared.")
        print("--- [CONTROL] Active Customers cleared ---")

    elif command == '.avoid':
        if args:
            unwanted_requests.append(args)
            await event.edit(f"🎯 **UNWANTED REQUESTS ENABLED**: Not accepting orders containing: **'{args}'**")
            print(f"--- [CONTROL] Unwanted Requests Set to '{args}' ---")
        else:
            await event.edit("⚠️ Please provide a keyword to use.    Usage: `.avoid <keyword>`")
            print("--- [CONTROL] Avoid Command Used Without Keyword ---")
    
    elif command == '.reset_unwanted':
        unwanted_requests = ["air", "ais", "ice", "tea"]
        await event.edit(f"🎯 **UNWANTED REQUESTS RESET**: Resetting Unwanted Requests to ['air', 'ais', 'ice', 'tea']")
        print(f"--- [CONTROL] Unwanted Requests are Reset ---")

    elif command == '.clear_customer':
        if not event.is_reply:
            await event.edit("⚠️ Reply to a customer's order template to clear them")
            return
        
        # Get the message you replied to
        reply_msg = await event.get_reply_message()
        
        # Get the string of the message
        target_text = reply_msg.raw_text.strip()
        
        # Search for the sender_id in customers based on the text
        found_id = None
        for sender_id, stored_msg in customers.items():
            if stored_msg.raw_text.strip() == target_text:
                found_id = sender_id
                break

        if found_id:
            del customers[found_id] 
            
            if len(customers) == 0:
                current_session_cafe = None

            if found_id in active_customers.keys():
                del active_customers[found_id]

            if found_id in replied_to:
                replied_to.remove(found_id)

            await event.edit(f"✅ Cleared Customer `{found_id}`")
            print(f"--- [CONTROL] Cleared customer: {found_id} ---")
        else:
            await event.edit("❌ No customer found with that text.")
            print("--- [CONTROL] .clear_customer : No match found ---")

    elif command == '.info':
        info_text = f"""📊 **SESSION INFO**
🏠 **Current Cafe:** `{current_session_cafe}`
👥 **Pending:** {len(customers)} | **Active:** {len(active_customers)}
💰 **Session Profit:** RM{session_total_profit}
🏍️ **Deliveries:** {session_total_delivery}"""
        await event.edit(info_text)
        print("--- [CONTROL] Info Displayed ---")

    elif command == '.setprice':
        if args:
            PRIVATE_RESPONSE = args.strip()
            await event.edit(f"💰 **PRICE UPDATED**: New response is: **'{PRIVATE_RESPONSE}'**")
            print(f"--- [CONTROL] Private Response Set to '{PRIVATE_RESPONSE}' ---")
        else:
            await event.edit(f"⚠️ Current price: **'{PRIVATE_RESPONSE}'**. Usage: `.setprice <new_response>`")
            print("--- [CONTROL] Setprice used without arguments ---")

    elif command == '.help':
        await event.edit(
""".help : Display all available commands
.info    : Show session summary
.pause   : Pause the bot 
.resume  : Resume the bot 
.status  : Tells the status of the bot 
.untrack : Clear tracking filter
.track   : Filter what you want
.done    : Finish the active delivery(s)
.active  : Set a delivery to active
.finish  : Finish the session
.avoid   : Add upon unwanted requests
.clear   : Clear the active customers
.setprice : Change the PM message
.clear_customer : Clear a specific customer
.reset_unwanted : Reset unwanted requests""")
        print(" --- [CONTROL] Display all available commands ---")



# ---------------------------------------------------------
# PART 2: THE TRIGGER (Group -> PM)
# ---------------------------------------------------------
@client.on(events.NewMessage(chats=TARGET_GROUP))
async def handler(event):
    global bot_active
    global current_session_cafe
    global places_outside_um
    
    # IMMEDIATE STOP if paused
    if not bot_active:
        return
    
    # 1. BUSY CHECK
    # Check total people (Active + Pending). If >= 2, we are full.
    total_people = len(customers)
    if total_people >= 2:
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
        if len(unwanted_requests) > 0:
            for unwanted in unwanted_requests:
                if unwanted.lower() in text.lower():
                    print(f"Filtered out a request containing '{unwanted}'. No PM sent.")
                    return
                
        # Filter requests that are too long
        dash_count = text.count('-')
        no_space_text = text.replace(" ", "")
        too_long = False

        if (dash_count > 3):
            too_long = True
        elif ("-3" in no_space_text or "-4" in no_space_text or "-5" in no_space_text):
            too_long = True
        elif ("-2" in no_space_text and dash_count == 3):
            too_long = True

        if (too_long):
            print("Filtered out a request that is too long. No PM sent.")
            return

        # --- CAFE MATCHING LOGIC ---
        # 1. Extract Cafe Name (simple parsing)
        # We look for "cafe:" OR "kafe:" and take the line
        extracted_cafe = None
        clean_text = text.lower().replace(" ", "")
        
        target_keyword = None
        if "cafe:" in clean_text:
            target_keyword = "cafe:"
        elif "kafe:" in clean_text:
            target_keyword = "kafe:"
            
        if target_keyword:
            try:
                # "ordertemplate...cafe:kk12\norder..." -> "kk12"
                part_after_cafe = clean_text.split(target_keyword)[1]
                extracted_cafe = part_after_cafe.split("\n")[0].strip()
            except:
                extracted_cafe = None


        # We lock here to prevent race conditions
        sender_id = event.sender_id
        
        async with processing_lock:
            # 1. BUSY CHECK (Re-check inside lock)
            total_people = len(customers)
            if total_people >= 2:
                print(f"⚠️ Busy with a customer. Ignoring request from {sender_id}")
                return
            
            # 2. Decision Logic

            # If customer is first (Total=0) Set the cafe
            if total_people == 0:
                current_session_cafe = extracted_cafe
                print(f"--- [LOGIC] First customer set Cafe to: {current_session_cafe} ---")

            # If customer is second (total=1) check if cafe match with customer 1
            elif total_people == 1:
                if not extracted_cafe or not current_session_cafe:
                    print(f"--- [LOGIC] Filtered! Cafe '{extracted_cafe}' does not match '{current_session_cafe}' ---")
                    return
                elif (extracted_cafe not in current_session_cafe) and (current_session_cafe not in extracted_cafe):
                    print(f"--- [LOGIC] Filtered! Cafe '{extracted_cafe}' does not match '{current_session_cafe}' ---")
                    return
                else:
                    print(f"--- [LOGIC] Match! Cafe '{extracted_cafe}' matches '{current_session_cafe}' ---")
            

            # Add them to our "Watch List"
            # STORE THE MESSAGE OBJECT (so we can forward it later)
            customers[sender_id] = event.message
            print(f"Trigger received from {sender_id}. Sending PM...")

        # If all filter is passed, proceed to send PM

        try:
            # Ensure we have the entity for sending
            await event.get_sender()

            # --- SAFETY MECHANISM: HUMAN DELAY ---
            # Wait 3 seconds before sending
            wait_time = 3
            print(f"   -> Waiting {wait_time} seconds to simulate human typing...")
            await asyncio.sleep(wait_time)

            # 3. Send the PRIVATE message

            # If message is requesting outside um, raise the price
            inside_um = all(x not in text.lower() for x in places_outside_um)

            if not inside_um:
                await client.send_message(sender_id, "Rm5?")
            else:
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
    global replied_to
    
    # 1. Check if bot is on and message is Private
    if not bot_active: return
    if not event.is_private: return

    # 2. IMPORTANT: Only reply if this person is in our "Customer List"
    # AND we haven't said "Ok" to them yet.
    sender_id = event.sender_id
    if sender_id not in customers or sender_id in replied_to:
        return

    # 3. Wait 3-5 seconds before replying to simulate human behavior
    wait_time = random.randint(3, 5)
    print(f"   -> Customer {sender_id} replied. Waiting {wait_time}s to say 'Ok'...")
    await asyncio.sleep(wait_time)

    # 4. Reply "Ok" or "rm4 sorry"
    try:
        if "3" in event.raw_text:
            await event.reply("rm4 sorry")
            print(f"   -> Replied 'rm4 sorry' to {sender_id}")
        else:
            await event.reply("Ok")
            print(f"   -> Replied 'Ok' to {sender_id}")
            
        replied_to.add(sender_id) # Mark as replied so we don't spam "Ok"

        # 5. FORWARDING LOGIC
        print(f"   -> Forwarding conversation to Saved Messages...")

        # A. Forward the Original Group Message (retrieved from memory)
        original_msg = customers[sender_id]
        await client.forward_messages('me', original_msg)

        # B. Forward the Customer's Reply (the current event)
        await client.forward_messages('me', event.message)
        
        # 6. We do NOT remove them here anymore. 
        # We wait for the user to type .active (to confirm order) or .done (to reset).
        # del customers[sender_id] 

        
    except Exception as e:
        print(f"   -> Error replying Ok: {e}")

print("Listening for 'ORDER TEMPLATE' requests...")
client.start()
client.run_until_disconnected()