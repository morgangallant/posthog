import { actions, connect, kea, key, listeners, path, props, reducers, selectors } from 'kea'
import type { consoleLogsListLogicType } from './consoleLogsListLogicType'
import { eventUsageLogic } from 'lib/utils/eventUsageLogic'
import {
    YesOrNoResponse,
    RecordingConsoleLog,
    RecordingSegment,
    RRWebRecordingConsoleLogPayload,
    RecordingWindowFilter,
    SessionRecordingPlayerProps,
    RecordingConsoleLogsFilters,
} from '~/types'
import { eventWithTime } from 'rrweb/typings/types'
import {
    getPlayerPositionFromEpochTime,
    getPlayerTimeFromPlayerPosition,
} from 'scenes/session-recordings/player/playerUtils'
import { colonDelimitedDuration } from 'lib/utils'
import { sharedListLogic } from 'scenes/session-recordings/player/list/sharedListLogic'
import { sessionRecordingDataLogic } from 'scenes/session-recordings/player/sessionRecordingDataLogic'
import { parseConsoleLogPayload } from 'scenes/session-recordings/player/list/consoleLogsUtils'
import Fuse from 'fuse.js'

const CONSOLE_LOG_PLUGIN_NAME = 'rrweb/console@1'

export const consoleLogsListLogic = kea<consoleLogsListLogicType>([
    path((key) => ['scenes', 'session-recordings', 'player', 'consoleLogsListLogic', key]),
    props({} as SessionRecordingPlayerProps),
    key((props: SessionRecordingPlayerProps) => `${props.playerKey}-${props.sessionRecordingId}`),
    connect(({ sessionRecordingId, playerKey }: SessionRecordingPlayerProps) => ({
        logic: [eventUsageLogic],
        values: [
            sessionRecordingDataLogic({ sessionRecordingId }),
            ['sessionPlayerData', 'filters'],
            sharedListLogic({ sessionRecordingId, playerKey }),
            ['windowIdFilter'],
        ],
        actions: [sessionRecordingDataLogic({ sessionRecordingId }), ['setFilters']],
    })),
    actions({
        submitFeedback: (feedback: YesOrNoResponse) => ({ feedback }),
        setConsoleListLocalFilters: (filters: Partial<RecordingConsoleLogsFilters>) => ({ filters }),
    }),
    reducers({
        consoleListLocalFilters: [
            {} as Partial<RecordingConsoleLogsFilters>,
            {
                setConsoleListLocalFilters: (state, { filters }) => ({ ...state, ...filters }),
            },
        ],
        feedbackSubmitted: [
            false,
            {
                submitFeedback: () => true,
            },
        ],
    }),
    listeners(({ values, actions }) => ({
        setConsoleListLocalFilters: async (_, breakpoint) => {
            await breakpoint(250)
            actions.setFilters(values.consoleListLocalFilters)
        },
        submitFeedback: ({ feedback }) => {
            eventUsageLogic.actions.reportRecordingConsoleFeedback(
                values.consoleListData.length,
                feedback,
                'Are you finding the console log feature useful?'
            )
        },
    })),
    selectors({
        consoleListData: [
            (s) => [s.sessionPlayerData, s.filters, s.windowIdFilter],
            (sessionPlayerData, filters, windowIdFilter): RecordingConsoleLog[] => {
                const logs: RecordingConsoleLog[] = []

                // Filter only snapshots from specified window
                const filteredSnapshotsByWindowId =
                    windowIdFilter === RecordingWindowFilter.All
                        ? sessionPlayerData.snapshotsByWindowId
                        : { [windowIdFilter]: sessionPlayerData.snapshotsByWindowId?.[windowIdFilter] }

                sessionPlayerData.metadata.segments.forEach((segment: RecordingSegment) => {
                    filteredSnapshotsByWindowId[segment.windowId]?.forEach((snapshot: eventWithTime) => {
                        if (
                            snapshot.type === 6 && // RRWeb plugin event type
                            snapshot.data.plugin === CONSOLE_LOG_PLUGIN_NAME &&
                            snapshot.timestamp >= segment.startTimeEpochMs &&
                            snapshot.timestamp <= segment.endTimeEpochMs
                        ) {
                            const parsed = parseConsoleLogPayload(
                                snapshot.data.payload as RRWebRecordingConsoleLogPayload
                            )

                            const playerPosition = getPlayerPositionFromEpochTime(
                                snapshot.timestamp,
                                segment.windowId,
                                sessionPlayerData.metadata.startAndEndTimesByWindowId
                            )
                            const playerTime = playerPosition
                                ? getPlayerTimeFromPlayerPosition(playerPosition, sessionPlayerData.metadata.segments)
                                : null

                            logs.push({
                                ...parsed,
                                playerTime,
                                playerPosition,
                                colonTimestamp: colonDelimitedDuration(Math.floor((playerTime ?? 0) / 1000)),
                            })
                        }
                    })
                })
                return filters?.query
                    ? new Fuse<RecordingConsoleLog>(logs, {
                          threshold: 0.3,
                          keys: ['rawString'],
                          findAllMatches: true,
                          ignoreLocation: true,
                          sortFn: (a, b) => {
                              const byScore = a.score - b.score
                              return logs[a.idx].playerTime && logs[b.idx].playerTime
                                  ? (logs[a.idx].playerTime as number) - (logs[b.idx].playerTime as number) || byScore
                                  : byScore
                          },
                      })
                          .search(filters.query)
                          .map((result) => result.item)
                    : logs
            },
        ],
    }),
])
