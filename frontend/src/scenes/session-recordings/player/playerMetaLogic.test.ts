import { expectLogic } from 'kea-test-utils'
import { initKeaTests } from '~/test/init'
import { sessionRecordingDataLogic } from 'scenes/session-recordings/player/sessionRecordingDataLogic'
import { sessionRecordingPlayerLogic } from 'scenes/session-recordings/player/sessionRecordingPlayerLogic'
import { playerMetaLogic } from 'scenes/session-recordings/player/playerMetaLogic'
import recordingMetaJson from '../__mocks__/recording_meta.json'
import recordingEventsJson from '../__mocks__/recording_events.json'
import recordingSnapshotsJson from '../__mocks__/recording_snapshots.json'
import { useMocks } from '~/mocks/jest'

const playerProps = { sessionRecordingId: '1', playerKey: 'playlist' }

describe('playerMetaLogic', () => {
    let logic: ReturnType<typeof playerMetaLogic.build>

    beforeEach(() => {
        useMocks({
            get: {
                '/api/projects/:team/session_recordings/:id': { result: recordingMetaJson },
                '/api/projects/:team/session_recordings/:id/snapshots/': { result: recordingSnapshotsJson },
                '/api/projects/:team/events': { results: recordingEventsJson },
            },
        })
        initKeaTests()
        logic = playerMetaLogic(playerProps)
        logic.mount()
    })

    describe('core assumptions', () => {
        it('mounts other logics', () => {
            expectLogic(logic).toMount([
                sessionRecordingDataLogic(playerProps),
                sessionRecordingPlayerLogic(playerProps),
            ])
        })
        it('starts with loading state', () => {
            expectLogic(logic).toMatchValues({
                loading: true,
            })
        })
    })

    describe('loading state', () => {
        it('stops loading after meta load is successful', async () => {
            await expectLogic(logic, () => {
                sessionRecordingDataLogic(playerProps).actions.loadRecordingMeta()
            })
                .toDispatchActions(['loadRecordingMetaSuccess'])
                .toMatchValues({ loading: false })
        })
    })
})
