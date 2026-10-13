"""Cover-grammar propagation preserves every prior and child flag/error state."""
import unittest
from esprima.parser import Parser


class CoverGrammarIdentityTests(unittest.TestCase):
    def test_prior_and_child_states_propagate(self):
        previous_error = object()
        child_error = object()
        result = object()
        for prior_binding in (False, True):
            for prior_target in (False, True):
                for prior_error in (None, previous_error):
                    for child_binding in (False, True):
                        for child_target in (False, True):
                            for error in (None, child_error):
                                parser = Parser('')
                                parser.context.isBindingElement = prior_binding
                                parser.context.isAssignmentTarget = prior_target
                                parser.context.firstCoverInitializedNameError = prior_error
                                def child():
                                    self.assertIs(parser.context.isBindingElement, True)
                                    self.assertIs(parser.context.isAssignmentTarget, True)
                                    self.assertIsNone(parser.context.firstCoverInitializedNameError)
                                    parser.context.isBindingElement = child_binding
                                    parser.context.isAssignmentTarget = child_target
                                    parser.context.firstCoverInitializedNameError = error
                                    return result
                                self.assertIs(parser.inheritCoverGrammar(child), result)
                                self.assertIs(parser.context.isBindingElement, prior_binding and child_binding)
                                self.assertIs(parser.context.isAssignmentTarget, prior_target and child_target)
                                self.assertIs(parser.context.firstCoverInitializedNameError, prior_error if prior_error is not None else error)


if __name__ == '__main__':
    unittest.main()
