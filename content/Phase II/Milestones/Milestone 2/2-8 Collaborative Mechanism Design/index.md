---
title: "2.8 Collaborative Mechanism Design"
description: "The interface that takes a proposed reward mechanism through the same sweep and analysis as the four designs, and the first timed evaluation."
status: in progress
source: signed-grant-agreement
tags: ["mechanism-design", "issuance-and-rewards"]
---

## Contract requirement

> Support for evaluating alternative reward mechanisms proposed by Avalanche or external teams

Milestone 2 success criterion:

> Sensitivity Analysis Report delivered covering all key parameters

Quoted from the [Signed Grant Agreement](/Phase-II/Milestones/Milestone-0/Signed-Grant-Agreement).

## Status

In progress. The mechanism interface is delivered, and the four designs of deliverable [2.2](/Phase-II/Milestones/Milestone-2/2-2-Simulation-Execution/) run through it. The [Sensitivity Analysis Report](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/) describes the interface in its section on the sweep. The first timed evaluation, of revenue-funded rewards, runs from 2 to 6 November 2026.

## Result

A new reward design enters the model as one rule. Any rule that turns a commitment's stake, duration, start date and the node's completed periods into a reward is written as one class of the model's reward interface. The class has bounded parameters and a check that rejects a rate that falls with duration or turns negative. The interface swaps the reward function without restructuring the simulation, as the agreement requires. Each of the four designs tested in Milestone 2 is such a class, and so is the chain's own rule.

A proposal from the Foundation or an outside team is written the same way. The proposal is given a neutral setting that reproduces the chain's rule, which checks the implementation, and then run through the same sweep and the same analysis as the four designs. Its output takes the agreement's form: correlation tables for every measure, a confidence rating on each relationship, and recommendation tiers.

## Next step

The first timed evaluation runs from 2 to 6 November 2026. The proposal is revenue-funded rewards, which the Foundation has raised, and the evaluation goes from request to reviewed results within five business days. Paying validators the network's fees serves as its comparison. The results are ready before Workshop 1 on 13 November.
