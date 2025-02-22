import socket
import threading
import time
from datetime import datetime

#  Define mandatory peers (IP, Port)
MANDATORY_PEERS = [("10.206.4.122", 1255), ("10.206.5.228", 6555)]

class PeerToPeerChat:
    def __init__(self, team_name, port):
        self.team_name = team_name
        self.port = port
        self.peers = set()
        self.sent_peers = set()  # Track peers that this peer has sent messages to
        self.message_history = []
        self.my_address = f"{socket.gethostbyname(socket.gethostname())}:{self.port}"

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", port))
        self.server_socket.listen(5)

        print(f"\n Server started, listening on port {port}...")
        threading.Thread(target=self.listen_for_connections, daemon=True).start()
        #threading.Thread(target=self.periodic_health_check, daemon=True).start()
        self.connect_to_mandatory_peers()

    def connect_to_mandatory_peers(self):
        print("\n [INFO] Attempting to connect to the mandatory peers...\n")
        for ip, peer_port in MANDATORY_PEERS:
            if self.health_check_peer(ip, peer_port):
                self.send_message(ip, peer_port, "sent connection!")
                self.peers.add(f"{ip}:{peer_port}")  # Add to peers if connected
                print(f"[INFO] Connected to {ip}:{peer_port} and added to peers list.")
            else:
                print(f"[WARN] Could not reach mandatory peer {ip}:{peer_port}. Not added to peers list.")

    def health_check_peer(self, ip, port):
        try:
            send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            send_socket.settimeout(5)  # Timeout after 5 seconds
            send_socket.connect((ip, port))
            send_socket.close()
            return True  # Peer is responsive
        except socket.timeout:
            return False  # Peer is not responsive
        except Exception as e:
            print(f"[ERROR] Health check failed for {ip}:{port} - {e}")
            return False

    def periodic_health_check(self):
        while True:
            time.sleep(60)  # Check every 60 seconds
            for ip, peer_port in MANDATORY_PEERS:
                if not self.health_check_peer(ip, peer_port):
                    print(f"[INFO] Removing unreachable mandatory peer {ip}:{peer_port}")
                    self.peers.discard(f"{ip}:{peer_port}")

    def listen_for_connections(self):
        while True:
            try:
                client_socket, addr = self.server_socket.accept()
                threading.Thread(target=self.handle_client, args=(client_socket,), daemon=True).start()
            except Exception as e:
                print(f"[ERROR] Connection error: {e}")

    def handle_client(self, client_socket):
     try:
        while True:
            message = client_socket.recv(1024).decode()
            if not message:
                break

            sender_info, team, msg = message.split(" ", 2)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            receiver_info = self.my_address

            if msg.strip().upper() == "EXIT":
                    if sender_info in self.peers:
                        self.peers.remove(sender_info)
                        print(f"\n [INFO] {sender_info} disconnected.")

            elif msg.strip() == "[PEER_QUIT]":
                if sender_info in self.peers:
                    self.peers.discard(sender_info)  # Remove the quitting peer
                    print(f"\n[INFO] Peer {sender_info} has exited. Removed from peer list.")
            else:
                # Add sender to known peers if it's not the current peer
                if sender_info != self.my_address:
                    self.peers.add(sender_info)

                self.message_history.append((timestamp, sender_info, receiver_info, f"(Received) {msg}"))
                print(f"\n[{timestamp}] [{sender_info} -> {receiver_info}] Received: {msg}")
                self.sent_peers.add(sender_info)

     except Exception as e:
        print(f"[ERROR] Receiving message error: {e}")
     finally:
        client_socket.close()


    def send_message(self, recipient_ip, recipient_port, message):
        try:
            sender_info = self.my_address
            recipient_info = f"{recipient_ip}:{recipient_port}"
            formatted_message = f"{sender_info} {self.team_name} {message}"

            send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            send_socket.settimeout(5)
            send_socket.connect((recipient_ip, recipient_port))
            send_socket.sendall(formatted_message.encode())
            send_socket.close()

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.message_history.append((timestamp, sender_info, recipient_info, f"(Sent) {message}"))
            self.sent_peers.add(recipient_info)
        except Exception as e:
            print(f" [TIMEOUT] Peer {recipient_ip}:{recipient_port} did not respond.")
    
    def connect_to_all_peers(self):
        if not self.peers:
            print("\n No connected peers to reconnect.")
            return
        
        print("\n Attempting to connect to all known peers...")
        for peer in self.peers:
            ip, port = peer.split(":")
            self.send_message(ip, int(port), "sent connection!")
            
    def notify_exit(self):
        """Notifies all connected peers and all peers we have sent messages to that this peer is quitting."""
        print("\n[INFO] Notifying all peers before quitting...")
        all_peers_to_notify = self.peers.union(self.sent_peers)  # Combine connected and sent peers
        
        # Notify both connected and sent peers
        for peer in all_peers_to_notify:
            peer_ip, peer_port = peer.split(":")
            self.send_message(peer_ip, int(peer_port), "[PEER_QUIT]")

        # Remove self from both connected and sent peers in all peers' lists
        for peer in all_peers_to_notify:
            peer_ip, peer_port = peer.split(":")
            self.remove_peer_from_other(peer_ip, peer_port)
        
        # Optionally clear sent_peers after quitting
        self.sent_peers.clear()

    def remove_peer_from_other(self, peer_ip, peer_port):
        """Remove self from the other peer's connected list if they have it"""
        # Sending the "PEER_QUIT" message so the other peer knows we are quitting
        try:
            self.send_message(peer_ip, peer_port, "[PEER_QUIT]")

        except Exception as e:
            print(f"[ERROR] Removing from other peer {peer_ip}:{peer_port}: {e}")

    def ping_peer(self, ip, port):
        """Tries to send a ping message to a peer to check if it's online."""
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(3)
            test_socket.connect((ip, port))
            test_socket.close()
            return True  # Peer is online
        except:
            return False  # Peer is offline

    def check_peer_active(self, ip, port):
        """Checks if the given peer is active before connecting."""
        if self.ping_peer(ip, port):
            print(f"\n[INFO] Peer {ip}:{port} is active and reachable!")
        else:
            print(f"\n[WARNING] Peer {ip}:{port} is NOT reachable.")


    def query_peers(self):
        if self.peers or MANDATORY_PEERS:
            print("\n Connected Peers:")
            for peer in self.peers:
                print(f" {peer} ")
        else:
            print("\n No connected peers.")

    def show_message_history(self):
        if self.message_history:
            print("\n ***** Message History *****")
            for timestamp, sender, recipient, message in self.message_history:
                print(f"[{timestamp}] {sender} -> {recipient}:{message}")
        else:
            print("\n No messages exchanged yet.")

    def run(self):
        while True:
            print("\n ***** Menu *****")
            print("1. Send message")
            print("2. Query connected peers")
            print("3. Connect to all peers")
            print("4. Check if peer is active")
            print("5. View message history")
            print("0. Quit")

            choice = input("Enter choice: ").strip()
            if choice == "1":
                recipient_ip = input("Enter recipient's IP address: ").strip()
                recipient_port = int(input("Enter recipient's port number: ").strip())
                message = input("Enter your message: ").strip()
                self.send_message(recipient_ip, recipient_port, message)
            elif choice == "2":
                self.query_peers()
            elif choice == "3":
                self.connect_to_all_peers()
            elif choice == "4":
                ip = input("Enter IP address: ").strip()
                port = int(input("Enter port number: ").strip())
                self.check_peer_active(ip,port)
            elif choice == "5":
                self.show_message_history()
            elif choice == "0":
                self.notify_exit()
                print("\nExiting...")
                break

if __name__ == "__main__":
    team_name = input("Enter your team name: ").strip()
    port = int(input("Enter your port number: ").strip())
    chat = PeerToPeerChat(team_name, port)
    chat.run()