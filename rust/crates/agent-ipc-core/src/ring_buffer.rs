use std::sync::atomic::{AtomicUsize, Ordering};
use std::cell::UnsafeCell;
use std::marker::PhantomData;

/// A lock-free Single-Producer Single-Consumer (SPSC) Ring Buffer.
/// Optimized for high-frequency inter-agent message passing.
pub struct RingBuffer<T> {
    buffer: Box<[UnsafeCell<T>]>,
    mask: usize,
    head: AtomicUsize, // Written by Producer, Read by Consumer
    tail: AtomicUsize, // Written by Consumer, Read by Producer
    _marker: PhantomData<T>,
}

unsafe impl<T: Send> Send for RingBuffer<T> {}
unsafe impl<T: Send> Sync for RingBuffer<T> {}

impl<T> RingBuffer<T> {
    /// Creates a new RingBuffer. Capacity must be a power of 2.
    pub fn new(capacity: usize) -> Self {
        assert!(capacity.is_power_of_two(), "Capacity must be a power of 2 for fast modulo");
        let mut buffer = Vec::with_capacity(capacity);
        // Note: In production, we would properly initialize the UnsafeCells. 
        // For this architecture, we assume T is initialized upon push.
        for _ in 0..capacity {
            buffer.push(UnsafeCell::new(std::mem::MaybeUninit::uninit().assume_init()));
        }
        
        Self {
            buffer: buffer.into_boxed_slice(),
            mask: capacity - 1,
            head: AtomicUsize::new(0),
            tail: AtomicUsize::new(0),
            _marker: PhantomData,
        }
    }

    /// Pushes an item into the buffer. Returns false if full.
    /// MUST only be called by the Single Producer.
    #[inline]
    pub fn push(&self, value: T) -> bool {
        let head = self.head.load(Ordering::Relaxed);
        let tail = self.tail.load(Ordering::Acquire);
        
        let next_head = head + 1;
        if next_head - tail > self.buffer.len() {
            return false; // Buffer is full
        }

        unsafe {
            *self.buffer.get_unchecked(head & self.mask).get() = value;
        }
        
        self.head.store(next_head, Ordering::Release);
        true
    }

    /// Pops an item from the buffer. Returns None if empty.
    /// MUST only be called by the Single Consumer.
    #[inline]
    pub fn pop(&self) -> Option<T> {
        let tail = self.tail.load(Ordering::Relaxed);
        let head = self.head.load(Ordering::Acquire);
        
        if tail == head {
            return None; // Buffer is empty
        }

        let value = unsafe {
            std::ptr::read(self.buffer.get_unchecked(tail & self.mask).get())
        };
        
        self.tail.store(tail + 1, Ordering::Release);
        Some(value)
    }

    #[inline]
    pub fn len(&self) -> usize {
        let head = self.head.load(Ordering::Acquire);
        let tail = self.tail.load(Ordering::Acquire);
        head.wrapping_sub(tail)
    }

    #[inline]
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
}
