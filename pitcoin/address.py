from datetime import datetime, timedelta
import threading
import random
import socket
import time

from net.clients import BitcoinClient
from net.exceptions import NodeDisconnected
from datatypes import messages

class Node(object):
    def __init__(self, ip_address, port, time):
        self.ip_address = ip_address
        self.port = port
        self.time = time

class AddressClient(BitcoinClient):
    def __init__(self, *args, **kwargs):
        from testnet import testnet
        if not testnet:
            super(AddressClient, self).__init__(*args, **kwargs)
        else:
            super(AddressClient, self).__init__(coin='bitcoin_testnet3', *args, **kwargs)

    def on_handshake(self):
        self.send_message(messages.GetAddr())

    def handle_addr(self, header, message):
        for message_address in message.addresses:
            AddressBook.addresses.append(Node(
                ip_address=message_address.address.ip_address,
                port=message_address.address.port,
                time=message_address.timestamp,
            ))

class AddressBook(threading.Thread):
    from testnet import testnet

    addresses = []
    if not testnet:
        seed_addresses = [
            "seed.bitcoin.sipa.be",
            "dnsseed.bluematt.me",
            "dnsseed.bitcoin.dashjr.org",
            "seed.bitcoinstats.com",
            "bitseed.xf2.org",
        ]
    else:
        seed_addresses = [
            "testnet-seed.bitcoin.petertodd.org",
            "testnet-seed.bluematt.me",
        ]

    @staticmethod
    def bootstrap():
        """
        Try to get addresses from a random seed node. This thread blocks on the loop, so run a separate one
        which will check if addresses are received or disconnect if timeout is reached.
        """
        bootstrapper = BootstrapperThread()
        bootstrapper.daemon = True
        bootstrapper.start()
        while len(AddressBook.addresses) == 0:
            try:
                current_seed = random.choice(AddressBook.seed_addresses)
                client = AddressClient(current_seed)
                bootstrapper.seed_client = client
                client.handshake()
                client.loop()
            except (NodeDisconnected, socket.error) as e:
                print("Connection to seed node '%s' failed: %s - retrying in 10 seconds." % (current_seed, e))
                time.sleep(10)

    @staticmethod
    def keep_updated():
        AddressBook.updater = AddressBook()
        AddressBook.updater.daemon = True
        AddressBook.updater.start()

    @staticmethod
    def get_node():
        viable_address = max(AddressBook.addresses, key=lambda a: a.time)
        AddressBook.addresses.remove(viable_address)
        return viable_address

    def run(self):
        pass

class BootstrapperThread(threading.Thread):
    """
    Runs a loop and disconnects from the current seed node whenever we either received the addresses
    we want or the timeout is reached
    """
    def __init__(self, *args, **kwargs):
        super(BootstrapperThread, self).__init__(*args, **kwargs)
        self.seed_client = None

    def run(self):
        timeout = datetime.now() + timedelta(seconds=40)
        while True:
            time.sleep(1)

            if len(AddressBook.addresses) > 0:
                # Ah, we've got some addresses, disconnect from the seed node and stop
                try:
                    if self.seed_client is not None:
                        self.seed_client.disconnect()
                except socket.error:
                    # The client may have already disconnected for some reason, or other error
                    pass
                return

            if datetime.now() > timeout:
                # Give up on the current seed node client and try the next one
                try:
                    if self.seed_client is not None:
                        self.seed_client.disconnect()
                except socket.error:
                    # The client may have already disconnected for some reason, or other error
                    pass
                timeout = datetime.now() + timedelta(seconds=10)
