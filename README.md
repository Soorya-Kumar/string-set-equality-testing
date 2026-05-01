# String Set Equality Testing (Las Vegas Algorithm)

This repository contains an implementation of a randomized Type-2 Las Vegas algorithm for testing the equality of elements between two sets of large integers. The algorithm is designed to identify whether there existing a matching element between two parties at the same index(Primary and Secondary) while minimizing the total number of bits exchanged.

## Overview

The project simulates a communication protocol between two threads (representing two remote databases). Each party holds a set of 10 integers, each $m$ bits long. The goal is to determine if there exists any index $k$ such that $u_k = v_k$.

### Key Features
- **Randomized Fingerprinting**: Uses modular arithmetic with random primes to create low-bit fingerprints of large numbers.
- **Bit Probing**: Randomly samples a single bit position to further differentiate values.
- **Multi-Round Filtering**:
  - **Round 1**: Initial filtering using a random prime $p$ and a single bit probe.
  - **Round 2**: Refined filtering using a second random prime $q$ and "quarter" checks (2-bit range indicators).
  - **Round 3**: Final verification where the Primary sends a full $m$-bit string to the Secondary for confirmation.
- **Communication Efficiency**: Tracks the total number of bits sent, aiming for a complexity of $m + O(\log m)$.
- **Las Vegas Property**: The algorithm always produces the correct answer ("YES" or "NO"), though the time/communication complexity is a random variable. If a false positive is detected, the protocol replies with '?' stating it's not sure of the answer.

## Algorithm Protocol

The logic follows this multi-round structure:

### Primary Thread
1. Pick a random prime $p$ and bit position $pos$.
2. Send $p$, $pos$, fingerprints ($u_k \mod p$), and bit probes to Secondary.
3. If Secondary finds matches:
   - If a single candidate is found, verify it immediately.
   - If multiple candidates ($K1$) are found, receive a bundle (prime $q$, fingerprints $v_k \mod q$, and quarters).
4. Filter candidates to get $K2$. If $K2$ is empty, output **NO**.
5. Pick a random $k^* \in K2$ and send the full string $u_{k^*}$ to Secondary for final confirmation.

### Secondary Thread
1. Receive Round 1 data. Identify candidate indices $K1$ where fingerprints and bit probes match.
2. If $K1$ is empty, send **NO_MATCH**.
3. If $|K1| = 1$, send the full value $v_k$ for a shortcut verification.
4. If $|K1| > 1$, pick a second prime $q$, compute fingerprints and quarters for all $k \in K1$, and send back to Primary.
5. Receive $u_{k^*}$ from Primary. If $u_{k^*} = v_{k^*}$, send **YES**; otherwise, signal a **RESTART**.

## Usage

### Prerequisites
- Python 3.x

### Running the Simulation
Execute the main script to start the interactive simulation:
```bash
python algo.v4.py
```

### Input Options
When prompted, you can:
- **Randomize**: Press ENTER to generate random sets $U$ and $V$ (the script plants a match at a random index for testing).
- **Manual Input**: Type `y` to manually enter 10 integers for both sets.
