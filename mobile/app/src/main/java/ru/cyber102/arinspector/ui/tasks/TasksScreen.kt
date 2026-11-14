package ru.cyber102.arinspector.ui.tasks

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.ImageLoader
import coil.compose.AsyncImage
import ru.cyber102.arinspector.R
import ru.cyber102.arinspector.data.model.ReportDto
import ru.cyber102.arinspector.ui.components.BrandTopBar
import ru.cyber102.arinspector.ui.components.EngineeringCard
import ru.cyber102.arinspector.ui.components.PrimaryActionButton
import ru.cyber102.arinspector.ui.components.ReportStatusBadge
import ru.cyber102.arinspector.ui.components.SeverityBadge
import ru.cyber102.arinspector.ui.theme.KstColors
import ru.cyber102.arinspector.ui.theme.PromScanShapesTokens
import ru.cyber102.arinspector.util.Formatters

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TasksScreen(
    viewModel: TasksViewModel,
    imageLoader: ImageLoader,
    onOpenTask: (String) -> Unit,
    onOpenSettings: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(Unit) {
        viewModel.loadReports(isPullRefresh = false)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(KstColors.Background)
    ) {
        BrandTopBar(
            title = stringResource(R.string.tasks_title),
            subtitle = stringResource(R.string.brand_company_subtitle),
            actions = {
                IconButton(
                    onClick = onOpenSettings,
                    modifier = Modifier
                        .size(48.dp)
                        .testTag("tasks_settings_button")
                ) {
                    Icon(
                        imageVector = Icons.Filled.Settings,
                        contentDescription = stringResource(R.string.cd_settings),
                        tint = KstColors.White
                    )
                }
            }
        )

        FilterChipsRow(
            selected = uiState.selectedFilter,
            onSelect = viewModel::selectFilter
        )

        PullToRefreshBox(
            isRefreshing = uiState.isRefreshing,
            onRefresh = { viewModel.loadReports(isPullRefresh = true) },
            modifier = Modifier.fillMaxSize()
        ) {
            when {
                uiState.isLoading && uiState.reports.isEmpty() -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        CircularProgressIndicator(color = KstColors.Accent)
                    }
                }
                uiState.errorMessage != null && uiState.reports.isEmpty() -> {
                    TasksErrorPlaceholder(
                        message = uiState.errorMessage.orEmpty(),
                        onRetry = { viewModel.loadReports(isPullRefresh = false) }
                    )
                }
                uiState.reports.isEmpty() -> {
                    TasksEmptyPlaceholder()
                }
                else -> {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        items(
                            items = uiState.reports,
                            key = { it.id ?: it.hashCode().toString() }
                        ) { report ->
                            TaskReportCard(
                                report = report,
                                photoUrl = viewModel.resolvePhotoUrl(report.photoUrl),
                                imageLoader = imageLoader,
                                onClick = {
                                    val id = report.id
                                    if (!id.isNullOrBlank()) {
                                        onOpenTask(id)
                                    }
                                }
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun FilterChipsRow(
    selected: TaskStatusFilter,
    onSelect: (TaskStatusFilter) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(KstColors.Surface)
            .horizontalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 10.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        val options = listOf(
            TaskStatusFilter.ALL to stringResource(R.string.tasks_filter_all),
            TaskStatusFilter.OPEN to stringResource(R.string.tasks_filter_open),
            TaskStatusFilter.IN_PROGRESS to stringResource(R.string.tasks_filter_in_progress),
            TaskStatusFilter.CLOSED to stringResource(R.string.tasks_filter_closed)
        )
        options.forEach { (filter, label) ->
            val isSelected = selected == filter
            FilterChip(
                selected = isSelected,
                onClick = { onSelect(filter) },
                label = {
                    Text(
                        text = label,
                        style = MaterialTheme.typography.labelLarge
                    )
                },
                shape = CircleShape,
                colors = FilterChipDefaults.filterChipColors(
                    containerColor = KstColors.Background,
                    labelColor = KstColors.TextSecondary,
                    selectedContainerColor = KstColors.Accent,
                    selectedLabelColor = KstColors.White
                ),
                border = FilterChipDefaults.filterChipBorder(
                    enabled = true,
                    selected = isSelected,
                    borderColor = KstColors.Border,
                    selectedBorderColor = KstColors.Accent
                ),
                modifier = Modifier.testTag("filter_chip_${filter.name.lowercase()}")
            )
        }
    }
}

@Composable
private fun TaskReportCard(
    report: ReportDto,
    photoUrl: String?,
    imageLoader: ImageLoader,
    onClick: () -> Unit
) {
    val equipmentTitle = report.result?.equipment?.name
        ?: report.equipmentId
        ?: "Оборудование"
    val criticality = report.result?.llm?.criticality
        ?: report.result?.defects?.firstOrNull()?.severity
        ?: "low"

    EngineeringCard(
        onClick = onClick,
        modifier = Modifier
            .fillMaxWidth()
            .testTag("task_card_${report.id ?: "unknown"}")
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.Top
        ) {
            if (!photoUrl.isNullOrBlank()) {
                AsyncImage(
                    model = photoUrl,
                    imageLoader = imageLoader,
                    contentDescription = equipmentTitle,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier
                        .size(78.dp)
                        .clip(PromScanShapesTokens.Control)
                        .border(1.dp, KstColors.Border, PromScanShapesTokens.Control)
                )
                Spacer(modifier = Modifier.width(12.dp))
            }

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = equipmentTitle,
                    style = MaterialTheme.typography.titleMedium,
                    color = KstColors.TextPrimary,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = Formatters.formatDateTime(report.createdAt),
                    style = MaterialTheme.typography.bodySmall,
                    color = KstColors.TextSecondary
                )
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    ReportStatusBadge(status = report.status)
                    SeverityBadge(severity = criticality)
                }
            }
        }
    }
}

@Composable
private fun TasksEmptyPlaceholder() {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        contentAlignment = Alignment.Center
    ) {
        EngineeringCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.fillMaxWidth(),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Icon(
                    painter = painterResource(R.drawable.ic_assignment),
                    contentDescription = null,
                    tint = KstColors.Accent,
                    modifier = Modifier.size(40.dp)
                )
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    text = stringResource(R.string.tasks_empty),
                    style = MaterialTheme.typography.titleMedium,
                    color = KstColors.TextPrimary
                )
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    text = stringResource(R.string.tasks_empty_hint),
                    style = MaterialTheme.typography.bodyMedium,
                    color = KstColors.TextSecondary,
                    textAlign = TextAlign.Center
                )
            }
        }
    }
}

@Composable
private fun TasksErrorPlaceholder(
    message: String,
    onRetry: () -> Unit
) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        contentAlignment = Alignment.Center
    ) {
        EngineeringCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.fillMaxWidth(),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Icon(
                    painter = painterResource(R.drawable.ic_cloud_off),
                    contentDescription = null,
                    tint = KstColors.Error,
                    modifier = Modifier.size(40.dp)
                )
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    text = message,
                    style = MaterialTheme.typography.bodyMedium,
                    color = KstColors.TextPrimary,
                    textAlign = TextAlign.Center
                )
                Spacer(modifier = Modifier.height(16.dp))
                PrimaryActionButton(
                    text = stringResource(R.string.tasks_retry),
                    onClick = onRetry,
                    modifier = Modifier.fillMaxWidth()
                )
            }
        }
    }
}
