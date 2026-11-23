module github.com/sancy1/flowsemantics/cdc/go

go 1.23

require github.com/sancy1/flowsemantics/go v0.0.0

// Pre-publish: resolve the module from the local source tree.
// Post-publish: delete this replace and require v0.1.0 instead.
replace github.com/sancy1/flowsemantics/go => ../../go
