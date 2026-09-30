//! Rust bindings for SALEHA Federated Learning Engine

use std::ffi::c_void;
use std::os::raw::{c_float, c_uint};

#[repr(C)]
pub struct FederatedConfig {
    pub model_dimension: usize,
    pub min_agents_per_round: usize,
    pub max_agents_per_round: usize,
    pub learning_rate: c_float,
    pub noise_multiplier: c_float,
    pub clipping_threshold: c_float,
    pub local_epochs: usize,
    pub batch_size: usize,
    pub enable_byzantine_robustness: bool,
    pub byzantine_tolerance: c_float,
}

extern "C" {
    fn saleha_federated_create(config: *const FederatedConfig) -> *mut c_void;
    fn saleha_federated_destroy(handle: *mut c_void);
    fn saleha_federated_initialize(handle: *mut c_void);
    fn saleha_federated_submit_update(
        handle: *mut c_void,
        agent_id: c_uint,
        gradients: *const c_float,
        gradient_len: usize,
        num_samples: u64,
        loss: c_float,
    ) -> i32;
    fn saleha_federated_aggregate(handle: *mut c_void, output: *mut c_float, output_len: usize) -> i32;
}

pub struct FederatedEngine {
    handle: *mut c_void,
    model_dimension: usize,
}

impl FederatedEngine {
    pub fn new(config: FederatedConfig) -> Self {
        let model_dimension = config.model_dimension;
        let handle = unsafe { saleha_federated_create(&config) };
        assert!(!handle.is_null(), "Failed to create federated engine");
        Self { handle, model_dimension }
    }
    
    pub fn initialize(&self) {
        unsafe { saleha_federated_initialize(self.handle) };
    }
    
    pub fn submit_update(
        &self,
        agent_id: u32,
        gradients: &[f32],
        num_samples: u64,
        loss: f32,
    ) -> Result<(), String> {
        let result = unsafe {
            saleha_federated_submit_update(
                self.handle,
                agent_id,
                gradients.as_ptr(),
                gradients.len(),
                num_samples,
                loss,
            )
        };
        
        if result == 0 {
            Ok(())
        } else {
            Err("Failed to submit update".to_string())
        }
    }
    
    pub fn aggregate(&self) -> Result<Vec<f32>, String> {
        let output_len = self.model_dimension;
        let mut output = vec![0.0f32; output_len];
        
        let result = unsafe {
            saleha_federated_aggregate(self.handle, output.as_mut_ptr(), output_len)
        };
        
        if result == 0 {
            Ok(output)
        } else {
            Err("Failed to aggregate".to_string())
        }
    }
}

impl Drop for FederatedEngine {
    fn drop(&mut self) {
        if !self.handle.is_null() {
            unsafe { saleha_federated_destroy(self.handle) };
        }
    }
}

unsafe impl Send for FederatedEngine {}
unsafe impl Sync for FederatedEngine {}
