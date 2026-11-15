package ru.cyber102.arinspector

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import kotlinx.coroutines.launch
import ru.cyber102.arinspector.data.repository.ApiResult
import ru.cyber102.arinspector.ui.components.EngineeringCard
import ru.cyber102.arinspector.ui.components.PrimaryActionButton
import ru.cyber102.arinspector.ui.components.SecondaryActionButton
import ru.cyber102.arinspector.ui.login.LoginScreen
import ru.cyber102.arinspector.ui.settings.ServerAddressDialog
import ru.cyber102.arinspector.ui.login.LoginViewModel
import ru.cyber102.arinspector.ui.scanner.ScannerScreen
import ru.cyber102.arinspector.ui.scanner.ScannerViewModel
import ru.cyber102.arinspector.ui.settings.SettingsScreen
import ru.cyber102.arinspector.ui.settings.SettingsViewModel
import ru.cyber102.arinspector.ui.tasks.TaskDetailScreen
import ru.cyber102.arinspector.ui.tasks.TaskDetailViewModel
import ru.cyber102.arinspector.ui.tasks.TasksScreen
import ru.cyber102.arinspector.ui.tasks.TasksViewModel
import ru.cyber102.arinspector.ui.theme.KstColors

object Routes {
    const val LOGIN = "login"
    const val SCANNER = "scanner"
    const val TASKS = "tasks"
    const val TASK_DETAIL = "task/{id}"
    const val SETTINGS = "settings"

    fun taskDetail(id: String): String = "task/$id"
}

@Composable
fun PromScanRootApp(container: AppContainer) {
    val navController = rememberNavController()
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    var isBootstrapping by remember { mutableStateOf(true) }
    var startDestination by remember { mutableStateOf(Routes.LOGIN) }

    LaunchedEffect(Unit) {
        startDestination = if (container.repository.hasStoredToken()) {
            when (val me = container.repository.fetchMe()) {
                is ApiResult.Success -> Routes.SCANNER
                is ApiResult.Error -> {
                    if (me.httpCode == 401) Routes.LOGIN else Routes.LOGIN
                }
            }
        } else {
            Routes.LOGIN
        }
        isBootstrapping = false
    }

    LaunchedEffect(Unit) {
        container.repository.unauthorizedEvents.collect {
            navController.navigate(Routes.LOGIN) {
                popUpTo(0) { inclusive = true }
            }
        }
    }

    if (isBootstrapping) {
        StartupSplash()
        return
    }

    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route
    val showBottomBar = currentRoute == Routes.SCANNER || currentRoute == Routes.TASKS
    val currentAccount by container.repository.currentAccount.collectAsStateWithLifecycle()

    Scaffold(
        containerColor = KstColors.Background,
        snackbarHost = { SnackbarHost(hostState = snackbarHostState) },
        bottomBar = {
            if (showBottomBar) {
                PromScanBottomBar(
                    currentRoute = currentRoute,
                    onNavigate = { targetRoute ->
                        navController.navigate(targetRoute) {
                            popUpTo(navController.graph.findStartDestination().id) {
                                saveState = true
                            }
                            launchSingleTop = true
                            restoreState = true
                        }
                    }
                )
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = startDestination,
            modifier = Modifier
                .fillMaxSize()
                .padding(bottom = innerPadding.calculateBottomPadding())
        ) {
            composable(Routes.LOGIN) {
                val vm: LoginViewModel = viewModel(
                    factory = LoginViewModel.Factory(container.repository)
                )
                val hasServerUrl by container.settingsStore.hasServerUrlFlow
                    .collectAsStateWithLifecycle(initialValue = true)
                if (!hasServerUrl) {
                    ServerAddressDialog(
                        onConfirm = { url ->
                            scope.launch { container.settingsStore.saveServerUrl(url) }
                        }
                    )
                }
                LoginScreen(
                    viewModel = vm,
                    onLoginSuccess = {
                        navController.navigate(Routes.SCANNER) {
                            popUpTo(Routes.LOGIN) { inclusive = true }
                        }
                    },
                    onOpenSettings = {
                        navController.navigate(Routes.SETTINGS)
                    }
                )
            }

            composable(Routes.SCANNER) {
                val canScan = currentAccount?.hasPermission("scan") ?: true
                if (!canScan) {
                    NoScanPermissionScreen(
                        onOpenSettings = { navController.navigate(Routes.SETTINGS) },
                        onLogout = {
                            scope.launch {
                                container.repository.logout()
                                navController.navigate(Routes.LOGIN) {
                                    popUpTo(0) { inclusive = true }
                                }
                            }
                        }
                    )
                } else {
                    val vm: ScannerViewModel = viewModel(
                        factory = ScannerViewModel.Factory(
                            repository = container.repository,
                            settingsStore = container.settingsStore
                        )
                    )
                    ScannerScreen(
                        viewModel = vm,
                        onOpenSettings = { navController.navigate(Routes.SETTINGS) },
                        onNavigateToTasks = {
                            navController.navigate(Routes.TASKS) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        onShowMessage = { msg ->
                            scope.launch {
                                snackbarHostState.showSnackbar(msg)
                            }
                        }
                    )
                }
            }

            composable(Routes.TASKS) {
                val vm: TasksViewModel = viewModel(
                    factory = TasksViewModel.Factory(container.repository)
                )
                TasksScreen(
                    viewModel = vm,
                    imageLoader = container.imageLoader,
                    onOpenTask = { id ->
                        navController.navigate(Routes.taskDetail(id))
                    },
                    onOpenSettings = { navController.navigate(Routes.SETTINGS) }
                )
            }

            composable(
                route = Routes.TASK_DETAIL,
                arguments = listOf(navArgument("id") { type = NavType.StringType })
            ) { backStackEntry ->
                val reportId = backStackEntry.arguments?.getString("id").orEmpty()
                val vm: TaskDetailViewModel = viewModel(
                    key = "task_$reportId",
                    factory = TaskDetailViewModel.Factory(reportId, container.repository)
                )
                TaskDetailScreen(
                    viewModel = vm,
                    imageLoader = container.imageLoader,
                    onBack = { navController.popBackStack() },
                    onShowMessage = { msg ->
                        scope.launch {
                            snackbarHostState.showSnackbar(msg)
                        }
                    }
                )
            }

            composable(Routes.SETTINGS) {
                val vm: SettingsViewModel = viewModel(
                    factory = SettingsViewModel.Factory(
                        settingsStore = container.settingsStore,
                        repository = container.repository
                    )
                )
                SettingsScreen(
                    viewModel = vm,
                    onBack = { navController.popBackStack() },
                    onLoggedOut = {
                        navController.navigate(Routes.LOGIN) {
                            popUpTo(0) { inclusive = true }
                        }
                    }
                )
            }
        }
    }
}

@Composable
private fun PromScanBottomBar(
    currentRoute: String?,
    onNavigate: (String) -> Unit
) {
    NavigationBar(
        containerColor = KstColors.Surface,
        tonalElevation = 0.dp
    ) {
        NavigationBarItem(
            selected = currentRoute == Routes.SCANNER,
            onClick = { onNavigate(Routes.SCANNER) },
            icon = {
                Icon(
                    painter = painterResource(R.drawable.ic_qr_scanner),
                    contentDescription = null,
                    modifier = Modifier.size(22.dp)
                )
            },
            label = { Text(stringResource(R.string.nav_scanner)) },
            colors = NavigationBarItemDefaults.colors(
                selectedIconColor = KstColors.Accent,
                selectedTextColor = KstColors.Accent,
                indicatorColor = KstColors.AccentTint,
                unselectedIconColor = KstColors.TextSecondary,
                unselectedTextColor = KstColors.TextSecondary
            ),
            modifier = Modifier.testTag("bottom_nav_scanner")
        )
        NavigationBarItem(
            selected = currentRoute == Routes.TASKS,
            onClick = { onNavigate(Routes.TASKS) },
            icon = {
                Icon(
                    painter = painterResource(R.drawable.ic_assignment),
                    contentDescription = null,
                    modifier = Modifier.size(22.dp)
                )
            },
            label = { Text(stringResource(R.string.nav_tasks)) },
            colors = NavigationBarItemDefaults.colors(
                selectedIconColor = KstColors.Accent,
                selectedTextColor = KstColors.Accent,
                indicatorColor = KstColors.AccentTint,
                unselectedIconColor = KstColors.TextSecondary,
                unselectedTextColor = KstColors.TextSecondary
            ),
            modifier = Modifier.testTag("bottom_nav_tasks")
        )
    }
}

@Composable
private fun StartupSplash() {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(KstColors.NavyDark),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = stringResource(R.string.brand_header_title),
                style = MaterialTheme.typography.headlineLarge,
                color = KstColors.White
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = stringResource(R.string.brand_company_subtitle),
                style = MaterialTheme.typography.bodyMedium,
                color = KstColors.White.copy(alpha = 0.78f)
            )
            Spacer(modifier = Modifier.height(24.dp))
            CircularProgressIndicator(
                color = KstColors.White,
                strokeWidth = 3.dp
            )
            Spacer(modifier = Modifier.height(12.dp))
            Text(
                text = stringResource(R.string.session_checking),
                style = MaterialTheme.typography.bodySmall,
                color = KstColors.White.copy(alpha = 0.78f)
            )
        }
    }
}

@Composable
private fun NoScanPermissionScreen(
    onOpenSettings: () -> Unit,
    onLogout: () -> Unit
) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(KstColors.Background)
            .padding(24.dp),
        contentAlignment = Alignment.Center
    ) {
        EngineeringCard(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = stringResource(R.string.access_no_scan_permission),
                style = MaterialTheme.typography.titleMedium,
                color = KstColors.TextPrimary,
                textAlign = TextAlign.Start
            )
            Spacer(modifier = Modifier.height(16.dp))
            PrimaryActionButton(
                text = stringResource(R.string.nav_settings),
                onClick = onOpenSettings,
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(modifier = Modifier.height(10.dp))
            SecondaryActionButton(
                text = stringResource(R.string.settings_logout),
                onClick = onLogout,
                modifier = Modifier.fillMaxWidth()
            )
        }
    }
}
