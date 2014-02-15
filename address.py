from datetime import datetime, timedelta
import threading
import random
import socket
import time

from protocoin.clients import BitcoinClient
from protocoin.datatypes import messages

from models import Node

class AddressClient(BitcoinClient):
    def __init__(self, *args, **kwargs):
        super(AddressClient, self).__init__(coin='bitcoin_testnet3', *args, **kwargs)

    def on_handshake(self):
        self.send_message(messages.GetAddr())

    def handle_addr(self, header, message):
        for message_address in message.addresses:
            AddressBook.addresses.append(Node(
                ip_address=message_address.address.ip_address,
                port=message_address.address.port,
                time=datetime.fromtimestamp(message_address.timestamp),
            ))

class AddressBook(threading.Thread):
    addresses = []
    seed_addresses = [
        # "vg.no",
        "as",

        # "seed.bitcoin.sipa.be",
        # "dnsseed.bluematt.me",
        # "dnsseed.bitcoin.dashjr.org",
        # "seed.bitcoinstats.com",
        # "bitseed.xf2.org",

        # Testnet
        # "testnet-seed.bitcoin.petertodd.org",
        # "testnet-seed.bluematt.me",
    ]

    @staticmethod
    def bootstrap():
        """
        Try to get addresses from a random seed node. This thread blocks on the loop, so run a separate one
        which will check if addresses are received or disconnect if timeout is reached.
        """
        bootstrapper = BootstrapperThread()
        bootstrapper.start()
        while len(AddressBook.addresses) == 0:
            try:
                client = AddressClient(random.choice(AddressBook.seed_addresses))
                bootstrapper.seed_client = client
                client.handshake()
                client.loop()
            except socket.error:
                pass

    @staticmethod
    def keep_updated():
        AddressBook.updater = AddressBook()
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
        timeout = datetime.now() + timedelta(seconds=5)
        while True:
            time.sleep(1)

            if len(AddressBook.addresses) > 0:
                # Ah, we've got some addresses, disconnect from the seed node and stop
                self.seed_client.disconnect()
                return

            if datetime.now() > timeout:
                # Give up on the current seed node client and try the next one
                self.seed_client.disconnect()
                timeout = datetime.now() + timedelta(seconds=10)
