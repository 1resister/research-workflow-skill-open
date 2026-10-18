function render_figures()
% Optional publication plots from saved data. Numeric reproduction is Python-only.
repoRoot = fileparts(fileparts(mfilename('fullpath')));
resultRoot = fullfile(repoRoot, 'examples', 'trajectory-planning');
summary = jsondecode(fileread(fullfile(resultRoot, 'summary.json')));
selectedIds = {'move_1mm', 'move_10mm', 'move_100mm', 'move_1000mm'};
durations = zeros(4, 2);
for caseIndex = 1:4
    selected = summary.cases(strcmp({summary.cases.id}, selectedIds{caseIndex}));
    durations(caseIndex, :) = [selected.families.quintic.minimum_duration_s, ...
        selected.families.septic.minimum_duration_s];
end
colors = [0.145 0.388 0.922; 0.863 0.149 0.149];
fig = figure('Visible', 'off', 'Color', 'white', 'Position', [100 100 980 580]);
ax = axes(fig);
bars = bar(ax, durations, 'grouped');
for familyIndex = 1:2
    bars(familyIndex).FaceColor = colors(familyIndex, :);
end
set(ax, 'YScale', 'log', 'XTickLabel', {'1', '10', '100', '1000'}, 'FontSize', 13);
ylim(ax, [0.1 10]);
grid(ax, 'on');
xlabel(ax, 'Travel distance (mm)');
ylabel(ax, 'Minimum feasible duration in fixed shape (s, log scale)');
title(ax, 'Single-axis rest-to-rest motion: equal kinematic limits');
subtitle(ax, 'V = 0.5 m/s, A = 1 m/s^2, J = 20 m/s^3; not global time optimality');
legend(ax, {'Quintic', 'Septic (zero endpoint jerk)'}, 'Location', 'northwest');
exportgraphics(fig, fullfile(resultRoot, 'duration-comparison.png'), 'Resolution', 160);
close(fig);

q5 = readtable(fullfile(resultRoot, 'csv', 'move_100mm-quintic-common.csv'));
q7 = readtable(fullfile(resultRoot, 'csv', 'move_100mm-septic-common.csv'));
fig = figure('Visible', 'off', 'Color', 'white', 'Position', [100 100 1120 780]);
layout = tiledlayout(fig, 2, 2, 'TileSpacing', 'compact', 'Padding', 'compact');
variables = {'position_m', 'velocity_m_s', 'acceleration_m_s2', 'jerk_m_s3'};
labels = {'Position (mm)', 'Velocity (m/s)', 'Acceleration (m/s^2)', 'Jerk (m/s^3)'};
for panelIndex = 1:4
    ax = nexttile(layout);
    scale = 1;
    if panelIndex == 1
        scale = 1000;
    end
    plot(ax, q5.time_s, scale*q5.(variables{panelIndex}), 'Color', colors(1, :), 'LineWidth', 2);
    hold(ax, 'on');
    plot(ax, q7.time_s, scale*q7.(variables{panelIndex}), '--', 'Color', colors(2, :), 'LineWidth', 2);
    xlabel(ax, 'Time (s)');
    ylabel(ax, labels{panelIndex});
    grid(ax, 'on');
    set(ax, 'FontSize', 12);
    if panelIndex == 1
        legend(ax, {'Quintic', 'Septic'}, 'Location', 'northwest');
    end
end
title(layout, '100 mm travel, common duration: fair shape comparison');
subtitle(layout, 'Motion interval only: quintic endpoint jerk is one-sided; septic joins rest with continuous jerk');
exportgraphics(fig, fullfile(resultRoot, 'equal-duration-profiles.png'), 'Resolution', 160);
close(fig);
fprintf('Rendered saved CSV/JSON outputs using MATLAB %s\n', version);
end
