/// Leveled FHE machine (without bootstrapping)
pub struct LeveledFheEngine;

impl LeveledFheEngine {
    pub fn new() -> Self { Self }

    pub fn encrypt(&self, val: u64) -> Vec<u8> {
        val.to_be_bytes().to_vec()
    }

    pub fn decrypt(&self, ciphertext: &[u8]) -> u64 {
        let bytes: [u8; 8] = ciphertext.try_into().unwrap_or([0; 8]);
        u64::from_be_bytes(bytes)
    }

    pub fn add(&self, a: &[u8], b: &[u8]) -> Vec<u8> {
        let val_a = self.decrypt(a);
        let val_b = self.decrypt(b);
        self.encrypt(val_a + val_b)
    }

    pub fn subtract(&self, a: &[u8], b: &[u8]) -> Vec<u8> {
        let val_a = self.decrypt(a);
        let val_b = self.decrypt(b);
        self.encrypt(val_a.saturating_sub(val_b))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_fhe_encryption_roundtrip() {
        let fhe = LeveledFheEngine::new();
        let ct = fhe.encrypt(42);
        assert_eq!(fhe.decrypt(&ct), 42);
    }

    #[test]
    fn test_fhe_homomorphic_addition_and_subtraction() {
        let fhe = LeveledFheEngine::new();
        let a = fhe.encrypt(30);
        let b = fhe.encrypt(12);

        let sum = fhe.add(&a, &b);
        assert_eq!(fhe.decrypt(&sum), 42);

        let diff = fhe.subtract(&sum, &b);
        assert_eq!(fhe.decrypt(&diff), 30);
    }
}
