"""AXI DMA 7.1 simple-mode polling. No imports with hardware side effects."""
import time

MAX_BYTES = (1 << 26) - 1
DDR_LIMIT = 0x20000000
ERROR_BITS = 0x70


def poll(predicate, timeout, label):
    deadline = time.monotonic() + timeout
    while True:
        value = predicate()
        if value:
            return value
        if time.monotonic() >= deadline:
            raise TimeoutError(label)
        time.sleep(0.00005)


def validate_transfer(address, length):
    if address < 0 or address % 4 or length <= 0 or length % 4:
        raise ValueError('DMA address and nonzero length must be 4-byte aligned')
    if length > MAX_BYTES or address + length > DDR_LIMIT:
        raise ValueError('DMA exceeds configured 26-bit length or HP1 DDR address range')


class PollingDMA:
    def __init__(self, mmio):
        self.mmio = mmio
        self.first = True

    def snapshot(self):
        return {hex(offset): hex(self.mmio.read(offset)) for offset in
                (0x00, 0x04, 0x18, 0x28, 0x30, 0x34, 0x48, 0x58)}

    def reset(self, timeout=2.0):
        self.mmio.write(0x00, 4)  # A soft reset applies to both DMA channels.
        poll(lambda: not ((self.mmio.read(0x00) | self.mmio.read(0x30)) & 4), timeout,
             'DMA reset did not clear')
        poll(lambda: (self.mmio.read(0x04) & 1) and (self.mmio.read(0x34) & 1), timeout,
             'DMA reset did not halt both channels')
        self.first = True

    def start(self, timeout=2.0):
        self.mmio.write(0x04, 0x7000)
        self.mmio.write(0x34, 0x7000)
        self.mmio.write(0x00, 1)
        self.mmio.write(0x30, 1)
        poll(lambda: not ((self.mmio.read(0x04) | self.mmio.read(0x34)) & 1), timeout,
             'DMA channel failed to start')

    def run(self, ip, width, height, tx_address, tx_bytes, rx_address, rx_bytes, timeout=5.0):
        if not 1 <= width <= 112 or not 1 <= height <= 112:
            raise ValueError('Invalid convolution dimensions')
        if tx_bytes != width * height * 12 or rx_bytes != ((width+1)//2) * ((height+1)//2) * 32 * 4:
            raise ValueError('Incorrect full-segment RGB-input/float-output stream lengths')
        validate_transfer(tx_address, tx_bytes)
        validate_transfer(rx_address, rx_bytes)
        if tx_address < rx_address + rx_bytes and rx_address < tx_address + tx_bytes:
            raise ValueError('TX and RX physical buffers overlap')
        tx_sr, rx_sr = self.mmio.read(0x04), self.mmio.read(0x34)
        if (tx_sr | rx_sr) & (ERROR_BITS | 1):
            raise RuntimeError('DMA halted or error before transfer: ' + repr(self.snapshot()))
        if not self.first and not (tx_sr & 2 and rx_sr & 2):
            raise RuntimeError('DMA is not idle before next transfer')
        if not (ip.read(0) & 4):
            raise RuntimeError('Convolution IP is not idle')
        self.mmio.write(0x04, 0x7000)
        self.mmio.write(0x34, 0x7000)
        ip.write(0x10, width)
        ip.write(0x18, height)
        self.mmio.write(0x18, tx_address)
        self.mmio.write(0x48, rx_address)
        # Arm RX before starting the producer; LENGTH must be the last channel setup write.
        started = time.perf_counter()
        self.mmio.write(0x58, rx_bytes)
        ip.write(0, 1)
        self.mmio.write(0x28, tx_bytes)
        done_seen = False
        def completed():
            nonlocal done_seen
            tx, rx, ctrl = self.mmio.read(0x04), self.mmio.read(0x34), ip.read(0)
            done_seen = done_seen or bool(ctrl & 2)
            if (tx | rx) & ERROR_BITS:
                raise RuntimeError('DMA transfer error: ' + repr(self.snapshot()))
            return done_seen and tx & 2 and rx & 2 and tx & 0x1000 and rx & 0x1000
        poll(completed, timeout, 'Convolution/DMA timeout: no complete output packet')
        elapsed_ms = (time.perf_counter() - started) * 1000
        if ip.read(0x20) != 0:
            raise RuntimeError('Convolution reported nonzero status')
        if self.mmio.read(0x58) != rx_bytes:
            raise RuntimeError('Received byte count does not match expected frame')
        self.first = False
        return elapsed_ms


def invalid_size_guard(ip, width, height, timeout=2.0):
    if not (ip.read(0) & 4):
        raise RuntimeError('IP not idle before invalid-size guard')
    ip.write(0x10, width)
    ip.write(0x18, height)
    ip.write(0, 1)
    poll(lambda: ip.read(0) & 2, timeout, 'Invalid-size guard did not complete')
    if ip.read(0x20) != 1:
        raise RuntimeError('Invalid-size guard status was not 1')
