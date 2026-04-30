import threading
import random
import queue
import sys

# ── Queues simulating communication channel ───────────────────────────────────
p2s = queue.Queue()   # Primary → Secondary
s2p = queue.Queue()   # Secondary → Primary

# ── Bit counter ───────────────────────────────────────────────────────────────
# Tracks the total number of bits 'transmitted' between threads to simulate 
# communication complexity. Uses a lock to ensure thread-safe updates.
bits_sent = 0
bits_lock = threading.Lock()

def send(q, msg, bits=0):
    """
    Simulates sending a message over a channel.
    Increments the global bit counter and puts the message in the queue.
    """
    global bits_sent
    with bits_lock:
        bits_sent += bits
    q.put(msg)

def log_bits(label, b):
    """
    Helper to record and print the number of bits sent in a specific step.
    Updates the global counter and provides a formatted log output.
    """
    global bits_sent
    with bits_lock:
        bits_sent += b
    print(f"[BITS] {label}: {b} bits  (total so far: {bits_sent})")

# ── Helpers ───────────────────────────────────────────────────────────────────
def is_prime(n):
    """Checks if a number n is prime using trial division up to sqrt(n)."""
    if n < 2: return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0: return False
    return True

def primes_in_range(lo, hi):
    """Returns a list of all prime numbers within the range [lo, hi]."""
    return [n for n in range(lo, hi + 1) if is_prime(n)]

def random_prime(lo, hi, exclude=None):
    """
    Selects a random prime from the range [lo, hi].
    Can optionally exclude a specific prime (e.g., to ensure p != q).
    """
    pool = [x for x in primes_in_range(lo, hi) if x != exclude]
    if not pool:
        raise ValueError(f"No primes found in [{lo}, {hi}] excluding {exclude}")
    return random.choice(pool)

def quarter(x, m):
    """
    Determines which quarter of the range [0, 2^m) the value x falls into.
    Used as an additional 2-bit filter to reduce false positives.
    Returns: 0, 1, 2, or 3.
    """
    size = (2 ** m) // 4
    return min(x // size, 3)

def bit_at(x, pos):
    """
    Extracts the bit at a specific position 'pos' (0-indexed from Least Significant Bit).
    Used for random single-bit probes to differentiate strings.
    """
    return (x >> pos) & 1

def bits_needed(n):
    """Calculates the minimum number of bits required to represent the integer n."""
    return max(1, n.bit_length())



# ── Input ─────────────────────────────────────────────────────────────────────
def get_input(m):

    print("\n╔══════════════════════════════════════════╗")
    print("║     Las Vegas String Matching Algorithm  ║")
    print("╚══════════════════════════════════════════╝\n")
    print(f"Each string is an integer in [0, 2^{m} - 1] = [0, {2**m - 1}]")
    print("Press ENTER to randomize all values.\n")

    choice = input("Manual input? (y/n): ").strip().lower()
    if choice != 'y':
        U = [random.randint(0, 2**m - 1) for _ in range(10)]
        V = [random.randint(0, 2**m - 1) for _ in range(10)]
        
        # Plant a match
        # REMOVE THIS IF DONT WANT TO SET A MATCH
        idx = random.randint(0, 9)
        V[idx] = U[idx]
        print(f"\n[SETUP] Randomized. Match planted at index {idx}.")
        return U, V

    print("\nEnter 10 integers for U (Primary), space-separated:")
    U = list(map(int, input("U: ").split()))
    print("Enter 10 integers for V (Secondary), space-separated:")
    V = list(map(int, input("V: ").split()))

    if len(U) != 10 or len(V) != 10:
        print("Need exactly 10 values each. Exiting.")
        sys.exit(1)

    max_val = 2**m - 1
    if any(x < 0 or x > max_val for x in U + V):
        print(f"All values must be in [0, {max_val}]. Exiting.")
        sys.exit(1)

    return U, V


# ── Primary Thread ────────────────────────────────────────────────────────────
def primary(U, m):
    run = 0
    while True:
        run += 1
        print(f"\n{'═'*55}")
        print(f"  RUN {run}")
        print(f"{'═'*55}")

        # ── Round 1: prime p + fingerprints + random bit probe ────────────────
        p = random_prime(m , 2 * m)
        bit_pos = random.randint(0, m - 1)   # random bit position to probe

        fingerprints_p = [u % p for u in U]
        bit_probes     = [bit_at(u, bit_pos) for u in U]

        print(f"\n[PRIMARY] Round 1:")
        print(f"          Prime p       = {p}")
        print(f"          Bit position  = {bit_pos}  (probing bit {bit_pos} of each string)")
        print(f"          Fingerprints  = {fingerprints_p}")
        print(f"          Bit probes    = {bit_probes}")

        bits_p      = bits_needed(p)
        bits_bitpos = bits_needed(bit_pos)      
        bits_fps    = 10 * bits_needed(p)       
        bits_bps    = 10 * 1                    
        round1_bits = bits_p + bits_bitpos + bits_fps + bits_bps
        log_bits("Round 1 (p + bit_pos + 10 fingerprints + 10 bit probes)", round1_bits)

        send(p2s, ("R1", p, bit_pos, fingerprints_p, bit_probes))

        # ── Receive response from Secondary ───────────────────────────────────
        msg = s2p.get()

        if msg[0] == "NO_MATCH":
            print(f"\n[PRIMARY] ✗ Output: NO — no k with uₖ = vₖ exists.")
            return

        if msg[0] == "SINGLE":
            # K1 had exactly one candidate — Secondary sends index + full value.
            # Primary checks exact match locally; no further messages needed.
            k, v_k = msg[1], msg[2]
            bits_single = bits_needed(k) + m
            log_bits(f"Round 2 shortcut (index + {m}-bit value for sole candidate k={k})", bits_single)
            if U[k] == v_k:
                print(f"\n[PRIMARY] ✓ Output: YES — u[{k}] = v[{k}]  (single-candidate shortcut)")
            else:
                print(f"\n[PRIMARY] ✗ False positive at k={k} (single-candidate). Restarting...\n")
            return

        # ("R2_BUNDLE", K1, q, fps_q, quarters_v)
        K1, q, fps_q, quarters_v = msg[1], msg[2], msg[3], msg[4]

        print(f"\n[PRIMARY] Round 2 received from Secondary:")
        print(f"          K1 candidates  = {K1}")
        print(f"          Prime q        = {q}")
        print(f"          Fingerprints q = {fps_q}")
        print(f"          Quarters       = {quarters_v}")

        # Primary filters K1 → K2 by checking U's fingerprints/quarters against
        # what Secondary sent (which were computed from V).
        K2 = []
        for i, k in enumerate(K1):
            if U[k] % q == fps_q[i] and quarter(U[k], m) == quarters_v[i]:
                K2.append(k)

        print(f"[PRIMARY] K2 (after filtering with q + quarters) = {K2}")

        # Cost calculation for Round 2 (Secondary → Primary):
        # - |K1| * log2(10) to send indices of candidates (approx 4 bits each)
        # - log2(q) for the second prime
        # - |K1| * log2(q) for the new fingerprints (v % q)
        # - |K1| * 2 bits for the 'quarter' filters
        bits_k1_idx = len(K1) * bits_needed(9)     # indices 0–9
        bits_q      = bits_needed(q)
        bits_fps_q  = len(K1) * bits_needed(q)
        bits_qtrs   = len(K1) * 2                  # 2 bits per quarter
        round2_bits = bits_k1_idx + bits_q + bits_fps_q + bits_qtrs
        log_bits(f"Round 2 (K1 indices + q + {len(K1)} fingerprints + {len(K1)} quarters)", round2_bits)

        if not K2:
            print(f"\n[PRIMARY] ✗ Output: NO — K2 empty after Round 2 filtering.")
            return

        # ── Round 3: pick random survivor, send full m-bit string ─────────────
        k_star = random.choice(K2)
        print(f"\n[PRIMARY] Round 3: K2={K2}, picked k*={k_star}, sending full u[{k_star}]={U[k_star]}")
        
        # Cost of Round 3: Sending one full m-bit integer for final verification.
        log_bits(f"Round 3 (full {m}-bit string u[{k_star}])", m)

        send(p2s, ("R3", k_star, U[k_star]))

        # ── Receive verdict ───────────────────────────────────────────────────
        verdict = s2p.get()
        if verdict[0] == "YES":
            print(f"\n[PRIMARY] ✓ Output: YES — u[{k_star}] = v[{k_star}]")
            return
        else:
            print(f"\n[PRIMARY] False positive at k*={k_star}. TRY AGAIN - NO DEFENTIVE ANSWER\n")

# ── Secondary Thread ──────────────────────────────────────────────────────────
def secondary(V, m):
    while True:
        # ── Round 1 ───────────────────────────────────────────────────────────
        msg = p2s.get()
        p, bit_pos, fps_p, bps = msg[1], msg[2], msg[3], msg[4]

        print(f"\n[SECONDARY] Round 1: received p={p}, bit_pos={bit_pos}")

        K1 = [k for k in range(10)
              if V[k] % p == fps_p[k] and bit_at(V[k], bit_pos) == bps[k]]

        print(f"[SECONDARY] K1 (after fingerprint + bit probe) = {K1}")

        if not K1:
            send(s2p, ("NO_MATCH",))
            print(f"[SECONDARY] K1 empty → NO_MATCH")
            return

        if len(K1) == 1:
            # Only one candidate — skip Round 2 entirely.
            # Send index + full m-bit value; Primary does exact match check.
            k = K1[0]
            print(f"[SECONDARY] K1 has single candidate k={k} → shortcut, sending v[{k}]={V[k]}")
            send(s2p, ("SINGLE", k, V[k]))
            return

        # ── Round 2: Secondary picks q, computes fingerprints + quarters, ──────
        # sends the whole bundle to Primary. Primary filters to get K2.
        # q is chosen from a distinct range and guaranteed != p.
        q = random_prime(m , 2 * m, exclude=p)
        fps_q     = [V[k] % q        for k in K1]
        quarters_v = [quarter(V[k], m) for k in K1]

        print(f"\n[SECONDARY] Round 2: picked q={q}, sending bundle to Primary")
        print(f"            K1={K1}, fingerprints q={fps_q}, quarters={quarters_v}")

        send(s2p, ("R2_BUNDLE", K1, q, fps_q, quarters_v))

        # ── Round 3 ───────────────────────────────────────────────────────────
        msg = p2s.get()
        if msg[0] != "R3":
            continue
        k_star, u_k = msg[1], msg[2]

        print(f"\n[SECONDARY] Round 3: received u[{k_star}]={u_k}, v[{k_star}]={V[k_star]}")

        if u_k == V[k_star]:
            send(s2p, ("YES",))
            print(f"[SECONDARY] ✓ Match confirmed at k={k_star}")
            return
        else:
            send(s2p, ("RESTART",))
            print(f"[SECONDARY] ✗ False positive at k={k_star}, restarting...")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    m = 128   # bit length; change as needed

    U, V = get_input(m)

    print(f"\n[SETUP] m = {m}")
    print(f"[SETUP] U = {U}")
    print(f"[SETUP] V = {V}\n")

    # Check ground truth
    true_matches = [k for k in range(10) if U[k] == V[k]]
    print(f"[SETUP] True matches at indices: {true_matches if true_matches else 'None'}")

    t1 = threading.Thread(target=primary,   args=(U, m))
    t2 = threading.Thread(target=secondary, args=(V, m))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    print(f"\n{'═'*55}")
    print(f"  TOTAL BITS EXCHANGED: {bits_sent}")
    print(f"  BUDGET:  m + O(log m) = {m} + O({m.bit_length()}) ≈ {m + 10 * m.bit_length()}")
    print(f"{'═'*55}\n")