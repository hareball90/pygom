"""
    .. moduleauthor:: Edwin Tye <Edwin.Tye@phe.gov.uk>

    Functions that is used to determine the composition of the 
    defined ode

"""
import re

from base_ode_model import BaseOdeModel
from transition import TransitionType

import sympy
import numpy

greekLetter = ('alpha','beta','gamma','delta','epsilon','zeta','eta','theta',
               'iota','kappa','lambda','mu','nu','xi','omicron','pi','rho',
               'sigma','tau','upsilon','phi','chi','psi','omega')

def generateTransitionGraph(odeModel, fileName=None):
    '''
    Generates the transition graph in graphviz given an ode model with transitions

    Parameters
    ----------
    odeModel: OperateOdeModel
        an ode model object
    fileName: str
        location of the file, if none entered, then the default directory is used
    
    Returns
    -------
    dot: graphviz object
    '''
    assert isinstance(odeModel, BaseOdeModel), "An ode model object required"

    from graphviz import Digraph
        
    if fileName is None:
        dot = Digraph(comment='ode model')
    else:
        dot = Digraph(comment='ode model', filename=fileName)
        
    dot.body.extend(['rankdir=LR'])
    
    param = [str(p) for p in odeModel.getParamList()]
    states = [str(s) for s in odeModel.getStateList()]

    for s in states:
        dot.node(s)

    transitionList = odeModel.getTransitionList()
    bdList = odeModel.getBirthDeathList()
    
    for transition in (transitionList + bdList):
        s1 = transition.getOrigState()
        eq = transition.getEquation()
        
        eq = _makeEquationPretty(eq, param)
        
        tType = transition.getTransitionType()
        if tType is TransitionType.T:
            s2 = transition.getDestState()
            dot.edge(s1, s2, label=eq)
        elif tType is TransitionType.B:
            # when we have a birth or death process, do not make the box
            dot.node(eq, shape="plaintext", width="0", height="0", margin="0")
            dot.edge(eq, s1)
        elif tType is TransitionType.D:
            dot.node(eq, shape="plaintext", width="0", height="0", margin="0")
            dot.edge(s1, eq)
        else:
            pass

    return dot

def _makeEquationPretty(eq, param):
    '''
    Make the equation suitable for graphviz format by converting
    beta to &beta;  and remove all the multiplication sign
    
    We do not process ** and convert it to a superscript because
    it is only possible with svg (which is a real pain to convert
    back to png) and only available from graphviz versions after
    14 Oct 2011
    '''
    for p in param:
        if p.lower() in greekLetter:
            eq = re.sub('(\W?)('+p+')(\W?)', '\\1&'+p+';\\3', eq)
    # eq = re.sub('\*{1}[^\*]', '', eq)
    # eq = re.sub('([^\*]?)\*([^\*]?)', '\\1 \\2', eq)
    # eq += " blah<SUP>Yo</SUP> + ha<SUB>Boo</SUB>"
    return eq

def generateDirectedDependencyGraph(odeMatrix, transitionList=None):
    '''
    Returns a binary matrix that contains the direction of the transition in
    a state 
    
    Parameters
    ----------
    odeMatrix: :class:`sympy.MutableDenseMatrix`
        A matrix of size [number of states x 1].  Obtained by invoking :meth:`OperateOdeModel.getOde`
    transitionList: list, optional
        list of transitions.  Can be generated by :func:`getMatchingExpressionVector`
    
    Returns
    -------
    G: :class:`numpy.ndarray`
        Two dimensional array of size [number of state x number of transitions] where each column has two entry,
        -1 and 1 to indicate the direction of the transition and the state.  All column sum to
        one, i.e. transition must have a source and target.
    '''
    assert isinstance(odeMatrix, sympy.MutableDenseMatrix), "Expecting a vector of expressions"
    
    if transitionList is None:
        transitionList = getMatchingExpressionVector(odeMatrix, True)
    else:
        assert isinstance(transitionList, list), "Require a list of transitions"
    
    B = numpy.zeros((len(odeMatrix), len(transitionList)))
    for i, a in enumerate(odeMatrix):
        for j, transitionTuple in enumerate(transitionList):
            t1, t2 = transitionTuple
            if _hasExpression(a, t1):
                B[i,j] += -1 # going out
            if _hasExpression(a, t2):
                B[i,j] += 1  # coming in
    return B

def getUnmatchedExpressionVector(exprVec, full_output=False):
    '''
    Return the unmatched expressions from a vector of equations
    
    Parameters
    ----------
    exprVec: :class:`sympy.MutableDenseMatrix`
        A matrix of size [number of states x 1].  
    full_output: bool, optional
        Defaults to False, if True, also output the list of matched expressions
    
    Returns
    -------
    list: 
        of unmatched expressions, i.e. birth or death processes
    '''
    assert isinstance(exprVec, sympy.MutableDenseMatrix), "Expecting a vector of expressions"
    
    transitionList = reduce(lambda x,y: x+y, map(getExpressions, exprVec))
    # transitionList = reduce(lambda x,y: x+y, [getExpressions(expr) for expr in exprVec])
    # transitionList = list()
    # for expr in exprVec:
    #     transitionList += getExpressions(expr)

    matchedTransitionList = _findMatchingExpression(transitionList)
    out = list(set(transitionList) - set(matchedTransitionList))

    if full_output:
        return out, _transitionListToMatchedTuple(matchedTransitionList)
    else:
        return out

def getMatchingExpressionVector(exprVec, outTuple=False):
    '''
    Return the matched expressions from a vector of equations
    
    Parameters
    ----------
    exprVec: :class:`sympy.MutableDenseMatrix`
        A matrix of size [number of states x 1].  
    outTuple: bool, optional
        Defaults to False, if True, the output is a tuple of length two
        which has the matching elements.  The first element is always
        positive and the second negative
    
    Returns
    -------
    list: 
        of matched expressions, i.e. transitions
    '''
    assert isinstance(exprVec, sympy.MutableDenseMatrix), "Expecting a vector of expressions"
    
    transitionList = list()
    for expr in exprVec:
        transitionList += getExpressions(expr)

    transitionList = list(set(_findMatchingExpression(transitionList)))

    if outTuple:
        return _transitionListToMatchedTuple(transitionList)
    else:
        return transitionList

def _findMatchingExpression(expressionList, full_output=False):
    '''
    Reduce a list of expressions to a list of transitions.  A transition
    is found when two expressions are identical with a change of sign.
    
    Parameters
    ----------
    expressionList: list
        the list of expressions
    full_output: bool, optional
        If True, output the unmatched expressions as well. Defaults to False.
        
    Returns
    -------
    list:
        of expressions that was matched
    '''
    tList = list()
    for i in range(len(expressionList)-1):
        for j in range(i+1, len(expressionList)):
            b = expressionList[i] + expressionList[j]
            if b == 0:
                tList.append(expressionList[i])
                tList.append(expressionList[j])

    if full_output:
        unmatched = set(expressionList) - set(tList)
        return tList, list(unmatched)
    else:
        return tList

def _transitionListToMatchedTuple(transitionList):
    '''
    Convert a list of transitions to a list of tuple, where each tuple
    is of length 2 and contains the matched transitions. First element
    of the tuple is the positive term
    '''
    tTupleList = list()
    for i in range(len(transitionList)-1):
        for j in range(i+1, len(transitionList)):
            b = transitionList[i] + transitionList[j]
            # the two terms cancel out
            if b == 0:
                if sympy.Integer(-1) in getLeafs(transitionList[i]):
                    tTupleList.append((transitionList[j], transitionList[i]))
                else:
#                     print transitionList[i]
#                     print sympy.Integer(-1) in getLeaf(transitionList[i])
#                     print getLeafs(transitionList[i])
                    tTupleList.append((transitionList[i], transitionList[j]))
    return tTupleList

def getExpressions(expr):
    inputDict = dict()
    _getExpression(expr.expand(), inputDict)
    return inputDict.keys()

def getLeafs(expr):
    inputDict = dict()
    _getLeaf(expr.expand(), inputDict)
    return inputDict.keys()

def _getLeaf(expr, inputDict):
    '''
    Get the leafs of an expression, can probably just do
    the same with expr.atoms() with most expression but we
    do not break down power terms i.e. x**2 will be broken
    down to (x,2) in expr.atoms() but this function will
    retain (x**2)
    '''
    t = expr.args
    tLengths = numpy.array(map(_expressionLength, t))
    
    for i, ti in enumerate(t):
        if tLengths[i] == 0:
            inputDict.setdefault(ti,0)
            inputDict[ti] += 1
        else:
            _getLeaf(ti, inputDict)
                
def _getExpression(expr, inputDict):
    '''
    all the operations is dependent on the conditions 
    whether all the elements are leafs or only some of them.
    Only return expressions and not the individual elements
    '''
    t = expr.args if len(expr.atoms()) > 1 else [expr]
    # print t
    
    # find out the length of the components within this node
    tLengths = numpy.array(map(_expressionLength, t))
    # print tLengths
    if numpy.all(tLengths == 0):
        # if all components are leafs, then the node is an expression
        inputDict.setdefault(expr, 0)
        inputDict[expr] += 1
    else:
        for i, ti in enumerate(t):
            # if the leaf is a singleton, then it is an expression
            # else, go further along the tree
            if tLengths[i] == 0:
                inputDict.setdefault(ti, 0)
                inputDict[ti] += 1
            else:
                if isinstance(ti, sympy.Mul):
                    _getExpression(ti, inputDict)
                elif isinstance(ti, sympy.Pow):
                    inputDict.setdefault(ti, 0)
                    inputDict[ti] += 1
                    
def _expressionLength(expr):
    '''
    Returns the length of the expression i.e. number of terms.
    If the expression is a power term, i.e. x^2 then we assume
    that it is one term and return 0. 
    '''
    # print type(expr)
    if isinstance(expr, sympy.Mul):
        return len(expr.args)
    elif isinstance(expr, sympy.Pow):
        return 0
    else:
        return 0

def _findIndex(eqVec, expr):
    '''
    Given a vector of expressions, find where you will locate the
    input term.
    
    Parameters
    ----------
    eqVec: :class:`sympy.MutableDenseMatrix`
        vector of sympy equation
    expr: sympy type
        An expression that we would like to find
        
    Returns
    -------
    list:
        of index that contains the expression.  Can be an empty list
        or with multiple integer
    '''
    out = list()
    for i, a in enumerate(eqVec):
        j = _hasExpression(a, expr)
        if j is True:
            out.append(i)
    return out

def _hasExpression(eq, expr):
    '''
    Test whether the equation eq has the expression expr
    '''
    out = False
    aExpand = eq.expand()
    if expr == aExpand:
        out = True
    if expr in aExpand.args:
        out = True
    return out

# def _obtainPureTransitionMatrix(odeObj):
#     '''
#     Get the pure transition matrix between states

#     Parameters
#     ----------
#     ode: :class:`.BaseOdeModel`
#        an ode object
#     Returns
#     -------
#     A: :class:`sympy.Matrix`
#         resulting transition matrix
#     remain: list
#         list of  which contains the unmatched
#         transitions
#     '''
#     A = odeObj.getOde()
#     termList = getMatchingExpressionVector(A, True)
#     T, remainTerms = _obtainPureTransitionMatrixFromOde(A, termList)
#     return T

def pureTransitionToOde(A):
    '''
    Get the ode from a pure transition matrix
    
    Parameters
    ----------
    A: `sympy.Matrix`
        a transition matrix of size [n \times n]

    Returns
    -------
    b: `sympy.Matrix`
        a matrix of size [n \times 1] which is the ode
    '''
    nrow, ncol = A.shape
    assert nrow == ncol, "Need a square matrix"
    B = [sum(A[:,i]) - sum(A[i,:]) for i in range(nrow)]
    return sympy.simplify(sympy.Matrix(B))

def stripBDFromOde(fx, bdList=None):
    if bdList is None:
        bdList = getUnmatchedExpressionVector(fx, False)

    fxCopy = fx.copy()
    for i, fxi in enumerate(fx):
        termInExpr = map(lambda x: x in fxi.expand().args, bdList)
        for j, term in enumerate(bdList):
            fxCopy[i] -= term if termInExpr[j]==True else 0
    
    # simplify converts it to an ImmutableMatrix, so we make it into
    # a mutable object again because we want the expanded form
    return sympy.Matrix(sympy.simplify(fxCopy)).expand()

def odeToPureTransition(fx, states, output_remain=False):
    bdList, termList = getUnmatchedExpressionVector(fx, full_output=True)
    fx = stripBDFromOde(fx, bdList)
    # we now have fx with pure transitions
    A, remainTermList = _singleOriginTransition(fx, termList, states)
    A, remainTermList = _odeToPureTransition(fx, remainTermList, A)
    # checking if our decomposition is correct
    fx1 = pureTransitionToOde(A)
    diffOde = sympy.simplify(fx - fx1)
    if numpy.all(numpy.array(map(lambda x: x == 0, diffOde)) == True):
        if output_remain:
            return A, remainTermList
        else:
            return A
    else:
        diffTerm = sympy.Matrix(filter(lambda x: x != 0, diffOde))
        diffTermList = getMatchingExpressionVector(diffTerm, True)
        diffTermList = map(lambda (x,y): (y,x), diffTermList)
        
        AA, remainTermList = _odeToPureTransition(diffOde, diffTermList, A)
        fx2 = pureTransitionToOde(AA)
        if output_remain:
            return AA, remainTermList
        else:
            return AA

def _odeToPureTransition(fx, termList=None, A=None):
    '''
    Get the pure transition matrix between states

    Parameters
    ----------
    fx: :class:`sympy.Matrix`
       input ode in symbolic form, f(x) 
    termList:
        list of two element tuples which contains the
        matching terms
    A:  `sympy.Matrix`, optional
        the matrix to be filled.  Defaults to None, which
        will lead to the creation of a [len(fx), len(fx)] matrix
        with all zero elements
    Returns
    -------
    A: :class:`sympy.Matrix`
        resulting transition matrix
    remain: list
        list of  which contains the unmatched
        transitions
    '''
    if termList is None:
        termList = getMatchingExpressionVector(fx, True)

    if A is None:
        A = sympy.zeros(len(fx), len(fx))
    
    remainTransition = list()
    for t1, t2 in termList:
        remain = True
        for i, aFrom in enumerate(fx):
            if _hasExpression(aFrom, t2):
                # arriving at
                for j, aTo in enumerate(fx):
                    if _hasExpression(aTo, t1):
                        A[i,j] += t1 # from i to j
                        remain = False
        if remain:
            remainTransition.append((t1, t2))
    
    return A, remainTransition

def _singleOriginTransition(fx, termList, states, A=None):
    if A is None:
        A = sympy.zeros(len(fx), len(fx))

    remainTermList = list()
    for k, transitionTuple in enumerate(termList):
        t1, t2 = transitionTuple    
        possibleOrigin = list()
        for i, s in enumerate(states):
            if s in t1.atoms():
                possibleOrigin.append(i)
        if len(possibleOrigin) == 1:
            for j, fxj in enumerate(fx):
                if possibleOrigin[0] != j and _hasExpression(fxj, t1):
                    A[possibleOrigin[0],j] += t1
                        # print t1, possibleOrigin, j, fxj, "\n"
        else:
            remainTermList.append(transitionTuple)

    return A, remainTermList

