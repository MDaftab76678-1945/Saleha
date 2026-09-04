//! Rust FFI bridge to C++ SNN Engine
//! Uses cbindgen to generate C header automatically

use std::ffi::c_void;
use std::os::raw::c_float;

#[repr(C)]
pub struct SNNEngineHandle {
    _private: [u8; 0],
}

extern "C" {
    fn nexus_snn_create(neuron_count: usize, use_gpu: bool) -> *mut SNNEngineHandle;
    fn nexus_snn_destroy(handle: *mut SNNEngineHandle);
    fn nexus_snn_infer(
        handle: *mut SNNEngineHandle,
        input: *const c_float,
        input_len: usize,
        timesteps: usize,
        output: *mut c_float,
        output_len: usize,
    ) -> i32;
}

/// Safe Rust wrapper around C++ SNN Engine
pub struct SNNInferenceEngine {
    handle: *mut SNNEngineHandle,
}

// SAFETY: The C++ implementation is thread-safe for const operations
unsafe impl Send for SNNInferenceEngine {}
unsafe impl Sync for SNNInferenceEngine {}

impl SNNInferenceEngine {
    pub fn new(neuron_count: usize, use_gpu: bool) -> Self {
        let handle = unsafe { nexus_snn_create(neuron_count, use_gpu) };
        assert!(!handle.is_null(), "Failed to create SNN engine");
        Self { handle }
    }

    pub fn infer(&self, input: &[f32], timesteps: usize) -> Vec<f32> {
        let neuron_count = input.len() / timesteps;
        let mut output = vec![0.0f32; neuron_count];
        
        let result = unsafe {
            nexus_snn_infer(
                self.handle,
                input.as_ptr(),
                input.len(),
                timesteps,
                output.as_mut_ptr(),
                output.len(),
            )
        };
        
        assert_eq!(result, 0, "SNN inference failed");
        output
    }
}

impl Drop for SNNInferenceEngine {
    fn drop(&mut self) {
        if !self.handle.is_null() {
            unsafe { nexus_snn_destroy(self.handle) };
        }
    }
}
