use trybuild::TestCases;

#[test]
fn test_unverified_task_cannot_be_dispatched() {
    let t = TestCases::new();
    // MUST fail to compile. If it passes, safety invariant is broken.
    t.compile_fail("tests/ui/unverified_dispatch.rs");
}

#[test]
fn test_verified_task_can_be_dispatched() {
    let t = TestCases::new();
    t.pass("tests/ui/verified_dispatch.rs");
}
