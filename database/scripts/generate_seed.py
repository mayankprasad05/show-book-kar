#!/usr/bin/env python3
"""Deterministic seed-data generator for show-book-kar.

Writes database/seed.sql. Load after schema.sql on an empty database.
"""
import random
import datetime

random.seed(7)

# Demo password for every seeded user: Passw0rd! (bcrypt, rounds=10).
# The digests are precomputed so seed.sql stays reproducible: bcrypt salts are
# random, so hashing at generation time would produce a different file each run.
DEMO_PASSWORD = "Passw0rd!"
HASHES = [
    "$2b$10$kpgRcv.StaUaa715h1pWY.scbrNwpQ2Y1gIHSPrEQfX0FdaSjLHdi",
    "$2b$10$OIRjseFssrW7zPvckFnRRekPmXqez1UbotjhxYNE7Tj6kGixmlS9y",
    "$2b$10$Wkeh9NiQamqbRVBykHlQEuVbpCw9lTPDLprD9g/WemKjU11Jl.ugi",
    "$2b$10$FKfoc5QUokSQsh6brUltGujv7XggwBu8r7vPtvt46b/R7N0L7Lphe",
    "$2b$10$bN/Ed7L.kCJTQqtnL7A4a.ZxwiWwOuUWcFG7hdmFhNtRlj3UvKBe.",
    "$2b$10$eP9Z0Mlrke0GSlPBssfMvuTRXBzjc6WHcFnBmNOM3V3CwFLwW5C.y",
    "$2b$10$03/rYj6H/AUCt/2g1/EeAOyUXDpShWf5pVMjO0tR90y2bn0PVwNyO",
    "$2b$10$5qsXrKwSWWfqW1A2hWBrcO1Sv4ssZi88GfTAxXxPcTLO87gzUPu3u",
    "$2b$10$M2nys9.30Yw5fR3JJ0Dp6OE0aIgIzn2TgnXHPch4YonvuGzHkj2Rm",
    "$2b$10$30mZ1oaCl4yQwjM3gbknsuIM6PBp8syntlep069jcGIK8.QReUWlu",
    "$2b$10$iI1zmYN5MUAnejoGZuNA0u/.xYFgmS39y1jUUyY.mtiQpLIk80SL.",
    "$2b$10$VfZQUa5s1GTHwrVYJzuyxeY3xXIuckZIRgd//7tEz2i4cdCecIiq.",
    "$2b$10$WoG58m5vmBtZ/rboHB1WteXA/x/T6hwfPHAXHIZIvV.gdVbMnxYEa",
    "$2b$10$nc6qnums/uvxMCRXtjmyM.gPao4rK42jHQLvLS.FvOgMqJ1jWf8QO",
    "$2b$10$Gg9OJwl5arFRFrk8/2991uNaRLoRmvIdjjfBUX7dbUevpt7gYTaEG",
    "$2b$10$G4mLwszcZbTmRTBazaeqquzGw9I7r4.6G3F1oUAoph4QesDCmTI5a",
    "$2b$10$AD3xVNiJw3OCu6j5Q4VMLOUpuBc5O3wZSDTMV7tFpNdPH8XVh54Ba",
]

def future(days_from, hour=10):
    return fmt(datetime.datetime(2026, 12, 15 + days_from, hour, 0))

def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S+0530")

I = []   # inserts: (table, list of tuples)
def ins(table, rows):
    I.append((table, rows))

def _m(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    return f"'{v}'"

def _mk(rows):
    return "(" + ", ".join(_m(v) for v in rows) + ")"

# Catalogue rows exist before anything else happens in the timeline.
now_ts = fmt(datetime.datetime(2026, 11, 1, 12, 0))

# ---------------- theatres / screens / seats ----------------
ins_rows = []
for i, (t, c) in enumerate([("PVR Inorbit", "Mumbai"),
                            ("PVR Priya", "Mumbai"),
                            ("PVR Spence", "Bengaluru"),
                            ("PVR Grand", "Delhi"),
                            ("PVR Liberty", "Chennai")], 1):
    ins_rows.append((i, t, c, now_ts))
ins("theatres", ins_rows)

SCN = [(1, "Screen 1", 120), (1, "Screen 2", 90),
       (2, "Screen 1", 80), (3, "Screen 1", 100),
       (4, "Screen 1", 150), (4, "Screen 2", 110),
       (5, "Screen 1", 90)]
ins("screens", [(i+1, name, tid, cap, now_ts) for (tid, name, cap), i in zip(SCN, range(len(SCN)))])

# SCR: (screen_id, theatre_id, name, capacity). screen_id is the real screens.id.
SCR = [(i + 1, tid, name, cap) for i, (tid, name, cap) in enumerate(SCN)]

# seats
row_labels = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "P", "Q", "R", "S", "T"]
SEAT = []
seat_id = 0
for screen_index, (sid, tid, name, capacity) in enumerate(SCR):
    # rows of varying width; consumed in order until capacity is reached
    layouts = [[(5, 12), (6, 14), (5, 12), (7, 16)],
               [(5, 12), (5, 12), (6, 14)],
               [(4, 10), (6, 14), (5, 12)],
               [(7, 16), (6, 14), (7, 16), (6, 14), (7, 16), (6, 14)],
               [(5, 12), (5, 12), (6, 14)],
               [(4, 10), (6, 14), (5, 12)],
               [(7, 16), (6, 14), (7, 16), (6, 14), (7, 16), (6, 14)]]
    layout = layouts[screen_index]
    placed = 0
    row_index = 0          # running row index per screen, so labels never repeat
    for (block_rows, seats_in_row) in layout:
        for _ in range(block_rows):
            if placed >= capacity or row_index >= len(row_labels):
                break
            label = row_labels[row_index]
            row_index += 1
            for j in range(1, seats_in_row + 1):
                if placed >= capacity:
                    break
                seat_id += 1
                typ = "vip" if (j == 1 or j == seats_in_row or row_index % 2 == 0) else "standard"
                SEAT.append((sid, label, j, typ, seat_id))
                placed += 1
        if placed >= capacity or row_index >= len(row_labels):
            break
ins("seats", [(s[4], s[0], s[1], s[2], s[3], now_ts) for s in SEAT])

# ---------------- movies ----------------
MOV = [("The Dark Knight","English",152),("Inception","English",148),
       ("Interstellar","English",169),("Dunkirk","English",106),("Tenet","English",150),
       ("Spider-Man: No Way Home","English",148),("Everything Everywhere All at Once","English",139),
       ("The Batman","English",176),("Black Widow","English",134),("Eternals","English",156),
       ("Venom: Let There Be Carnage","English",107),("Free Guy","English",115),
       ("Strange Planet","English",96),("Gadar 2","Hindi",169),("Watson","Hindi",145)]
ins("movies", [(i+1, t, l, d, now_ts) for i, (t, l, d) in enumerate(MOV)])

# ---------------- shows ----------------
shows_plan = []
for s in range(len(SCN)):
    for d in range(2, 5):
        for h in [10, 13, 16, 19]:
            if len(shows_plan) >= 12: break
            movie_idx = (s*2 + d) % 10
            shows_plan.append((s, d, h, movie_idx))
        if len(shows_plan) >= 12: break

SH = []   # (show_id, screen_id, movie_idx, start_dt, end_dt, price)
for (s, d, h, mi) in shows_plan:
    screen_id = SCR[s][0]      # s = screen index; use real screens.id
    dur = MOV[mi][2]
    st = __import__("datetime").datetime(2026, 12, d, h, 0)
    et = st + __import__("datetime").timedelta(minutes=dur)
    price = round(random.uniform(80.0, 260.0), 2)
    SH.append((len(SH)+1, screen_id, mi+1, st, et, price))
ins("shows", [(i+1, sh[2], sh[1], sh[3], sh[4], sh[5], now_ts) for i, sh in enumerate(SH)])

# show_seats are generated after bookings, so HELD/BOOKED rows can point at a
# real bookings.id (the schema rejects held_by_booking_id = 0).

# ---------------- users ----------------
CUST = [("Alice Sharma","alice@example.com"),("Bob Reddy","bob@example.com"),
        ("Carol Nair","carol@example.com"),("David Kulkarni","david@example.com"),
        ("Eve Desai","eve@example.com"),("Frank Rosario","frank@example.com"),
        ("Grace Iyer","grace@example.com"),("Henry Park","henry@example.com"),
        ("Iris Sato","iris@example.com"),("Jack Muller","jack@example.com"),
        ("Karen Lee","karen@example.com"),("Leo Tanaka","leo@example.com"),
        ("Mona Patel","mona@example.com"),("Nate Cooper","nate@example.com"),
        ("Olivia Gupta","olivia@example.com")]
ADMIN = [("Admin One","admin1@example.com"),("System Admin","admin2@example.com")]
USR = []
u_id = 0
for nm, em in CUST + ADMIN:
    u_id += 1
    role = "admin" if em in [a[1] for a in ADMIN] else "customer"
    USR.append((u_id, em, HASHES[u_id - 1], nm, role, now_ts))
ins("users", USR)

def seats_of_show(show):
    """(seat_id, price) for the first 16 seats of the show's screen, in order."""
    screen_id, price = show[1], show[5]
    screen_seats = [(s[4], s[2], s[1]) for s in SEAT if s[0] == screen_id]
    screen_seats.sort(key=lambda x: (x[2], x[1]))
    return [(s[0], price) for s in screen_seats[:16]]

# ---------------- bookings ----------------
# Bookings 1-4 are CONFIRMED (with a successful payment) and own their seats.
# Booking 5 is PENDING and owns a single live HELD seat.
BK = []
BSEATS = []      # (booking_id, show_id, seat_id, price)
state = {}       # (show_id, seat_id) -> (status, held_by_booking_id, hold_expires_at)
b_id = 0
for i in range(5):
    if i >= len(SH):
        break
    show = SH[i]
    show_id = show[0]
    avail = seats_of_show(show)
    if i < 4:
        uid = (i % len(CUST)) + 1
        n = 1 if i % 2 == 0 else 2
        bk_status, seat_status = "CONFIRMED", "BOOKED"
        created = fmt(datetime.datetime(2026, 11, 20, 18, 30))
    else:
        uid = 5
        n = 1
        bk_status, seat_status = "PENDING", "HELD"
        created = fmt(datetime.datetime(2026, 11, 22, 11, 30))

    chosen = avail[:n]
    b_id += 1
    total = round(sum(p for _, p in chosen), 2)
    BK.append((b_id, uid, show_id, bk_status, total, created))
    for seat_id_val, p in chosen:
        BSEATS.append((b_id, show_id, seat_id_val, p))
        state[(show_id, seat_id_val)] = (
            seat_status,
            b_id,
            # A seeded live hold stays valid until 5 minutes before its show.
            # It is deliberately long-lived so the demo can pay for it, and a
            # separate expired row can be created when testing release-expired.
            fmt(show[3] - datetime.timedelta(minutes=5)) if seat_status == "HELD" else None,
        )
ins("bookings", BK)

# ---------------- show_seats ----------------
SSE = []
for (show_id, screen_id, mi, st, et, price) in SH:
    for seat_id_val, _p in seats_of_show((show_id, screen_id, mi, st, et, price)):
        status, held_by, expires = state.get(
            (show_id, seat_id_val), ("AVAILABLE", None, None))
        SSE.append((show_id, seat_id_val, status, expires, price, held_by, st))
ins("show_seats", SSE)

# ---------------- booking_seats ----------------
ins("booking_seats", [(b, s, seat, p, now_ts) for (b, s, seat, p) in BSEATS])

# ---------------- payments (confirmed bookings only) ----------------
PAY = []
p_id = 0
for b in BK:
    if b[3] != "CONFIRMED":
        continue
    p_id += 1
    PAY.append((p_id, b[0], b[4], "SUCCESS", f"txn_{b[0]:04d}",
                fmt(datetime.datetime(2026, 11, 20, 19, 0))))
ins("payments", PAY)

# ---------------- refunds (a separate record, never over the paid amount) ----------
REF = []
if PAY:
    payment = PAY[0]
    booking = BK[0]
    REF.append((1, payment[0], booking[0],
                round(float(payment[2]) * 0.4, 2), "REQUESTED",
                "Customer requested refund",
                fmt(datetime.datetime(2026, 11, 24, 10, 0))))
ins("refunds", REF)

# ---------------- emit ----------------
def q(table, rows):
    return f"INSERT INTO {table} (id, {', '.join('col_%d'%i for i in range(len(rows[0])))}) VALUES {', '.join(_mk(r) for r in rows)};"

lines = ["-- ============================================================================",
         "-- Show-book-kar seed data (deterministic, random seed=7)",
         "-- Every seeded user shares the demo password: Passw0rd! (bcrypt)",
         "-- Owner: M | Reviewer: H, S",
         "-- ============================================================================",
         ""]
EMIT_ORDER = ["theatres", "screens", "seats", "movies", "shows", "users",
              "bookings", "show_seats", "booking_seats", "payments", "refunds"]
for table, rows in sorted(I, key=lambda kv: EMIT_ORDER.index(kv[0])):
    cols = ["id","name","city","created_at"] if table=="theatres" else \
           ["id","name","theatre_id","created_at"] if table=="screens" else \
           ["id","screen_id","row_label","seat_number","seat_type","created_at"] if table=="seats" else \
           ["id","title","language","duration_minutes","created_at"] if table=="movies" else \
           ["id","movie_id","screen_id","start_at","end_at","base_price","created_at"] if table=="shows" else \
           ["show_id","seat_id","status","hold_expires_at","price","held_by_booking_id","created_at"] if table=="show_seats" else \
           ["id","email","password_hash","name","role","created_at"] if table=="users" else \
           ["id","user_id","show_id","status","total_amount","created_at"] if table=="bookings" else \
           ["booking_id","show_id","seat_id","price","created_at"] if table=="booking_seats" else \
           ["id","booking_id","amount","status","transaction_ref","created_at"] if table=="payments" else \
           ["id","payment_id","booking_id","amount","status","reason","created_at"] if table=="refunds" else \
           [str(i) for i in range(len(rows[0]))]
    # build proper column list per table
    colmap = {"theatres": ["id","name","city","created_at"],
              "screens": ["id","name","theatre_id","capacity_total","created_at"],
              "seats": ["id","screen_id","row_label","seat_number","seat_type","created_at"],
              "movies": ["id","title","language","duration_minutes","created_at"],
              "shows": ["id","movie_id","screen_id","start_at","end_at","base_price","created_at"],
              "show_seats": ["show_id","seat_id","status","hold_expires_at","price","held_by_booking_id","created_at"],
              "users": ["id","email","password_hash","name","role","created_at"],
              "bookings": ["id","user_id","show_id","status","total_amount","created_at"],
              "booking_seats": ["booking_id","show_id","seat_id","price","created_at"],
              "payments": ["id","booking_id","amount","status","transaction_ref","created_at"],
              "refunds": ["id","payment_id","booking_id","amount","status","reason","created_at"]}
    cols = colmap[table]
    lines.append(f"INSERT INTO {table} ({', '.join(cols)}) VALUES {', '.join(_mk(r) for r in rows)};")
    lines.append("")
# Resync serial/identity sequences: explicit ids were inserted above, so the
# sequences must be moved past the highest id or later app inserts collide.
lines.append("-- ----------------------------------------------------------------------------")
lines.append("-- Resync id sequences after explicit ids were inserted.")
lines.append("-- ----------------------------------------------------------------------------")
lines.append("DO $$")
lines.append("DECLARE")
lines.append("    t TEXT;")
lines.append("    s TEXT;")
lines.append("    m BIGINT;")
lines.append("BEGIN")
lines.append("    FOREACH t IN ARRAY ARRAY['users', 'movies', 'theatres', 'screens',")
lines.append("                              'seats', 'shows', 'bookings', 'payments', 'refunds']")
lines.append("    LOOP")
lines.append("        s := pg_get_serial_sequence(t, 'id');")
lines.append("        EXECUTE format('SELECT COALESCE(MAX(id), 0) FROM %I', t) INTO m;")
lines.append("        IF s IS NOT NULL AND m > 0 THEN")
lines.append("            PERFORM setval(s, m);")
lines.append("        END IF;")
lines.append("    END LOOP;")
lines.append("END $$;")
lines.append("")

with open("database/seed.sql", "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines))
print("wrote database/seed.sql with", len(I), "tables")
