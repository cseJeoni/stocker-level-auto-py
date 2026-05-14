import socket
import time

# Equipment simulator for end-to-end testing of the measurement flow.

server_address = "127.0.0.1"
server_port = 5000

shelf_list = [
    "1-01-01", "1-01-02", "1-01-03", "1-01-04", "1-01-05",
    "1-01-06", "1-01-07", "1-01-08", "1-01-09", "1-01-10",
    "2-01-01", "2-01-02", "2-01-03", "2-01-04", "2-01-05",
    "2-01-06", "2-01-07", "2-01-08", "2-01-09", "2-01-10"
]

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((server_address, server_port))

try:
    for shelf in shelf_list:
        print(f"\n[SIM] Moving to shelf {shelf}...")
        time.sleep(2)  # Simulates travel and mechanical stabilization time

        # Send MEASURE command
        client_socket.sendall(f"MEASURE|{shelf}\n".encode("utf-8"))
        print(f"[SIM] MEASURE request sent for {shelf}.")

        # Send FINISH after 1 second as a step-completion trigger
        time.sleep(1)
        client_socket.sendall("FINISH\n".encode("utf-8"))
        print(f"[SIM] FINISH sent for {shelf}.")

except Exception as e:
    print(f"[SIM] Communication error: {e}")
finally:
    client_socket.close()
    print("\n[SIM] Disconnected.")