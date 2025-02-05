import { ActiveSession, UserSession, ChartSession, SessionType } from './sessions';

export class SessionFactory {
    createSession(type: SessionType, params: any): ActiveSession {
      const { userId, orgId, startTime, userActivitySeen, lastActivityTime, chartType, chartName } = params;
      switch (type) {
        case SessionType.UserSession:
          return new UserSession(userId, orgId, new Date(startTime), userActivitySeen, lastActivityTime ? new Date(lastActivityTime) : null);
        case SessionType.ChartSession:
          return new ChartSession(userId, orgId, chartType, chartName, new Date(startTime), userActivitySeen, lastActivityTime ? new Date(lastActivityTime) : null);
        default:
          throw new Error('Unknown session type');
      }
    }
  }